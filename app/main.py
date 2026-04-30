import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.state import race_state
from app.core.utils import parse_dt
from app.api.race import router as race_router
from app.services.session_resolver import resolve_race_session
from app.services.live_timing import start_live_timing
from app.services.broadcaster import broadcaster
from app.services.openf1_client import openf1_client
from app.services.sector_builder import build_latest_sectors
from app.services.driver_builder import build_driver_map
from app.services.position_builder import normalize_positions
from app.services.map_builder import extract_outline_points, build_car_positions
from app.services.weather_builder import latest_weather

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _load_track_outline(session_key: int, laps: list[dict]) -> None:
    """Fetch one reference lap of location data to draw the circuit outline."""
    if not laps or not race_state.normalized_positions:
        return

    ref_driver = race_state.normalized_positions[0]["driver"]["number"]
    ref_laps = sorted(
        [
            l for l in laps
            if l.get("driver_number") == ref_driver
            and not l.get("is_pit_out_lap")
            and l.get("date_start")
            and l.get("lap_duration")
        ],
        key=lambda l: l["lap_number"],
    )

    ref_lap = ref_laps[1] if len(ref_laps) >= 2 else (ref_laps[0] if ref_laps else None)
    if not ref_lap:
        logger.warning("No suitable reference lap found for track outline.")
        return

    start_dt = parse_dt(ref_lap["date_start"])
    end_dt   = start_dt + timedelta(seconds=float(ref_lap["lap_duration"]))

    outline_locs = await openf1_client.get_locations(
        session_key,
        driver_number=ref_driver,
        date_gte=start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        date_lte=end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    race_state.track_outline = extract_outline_points(outline_locs)
    logger.info("Track outline loaded: %d points.", len(race_state.track_outline))

    # Compute where each sector boundary falls as a fraction of the outline
    s1 = ref_lap.get("duration_sector_1")
    s2 = ref_lap.get("duration_sector_2")
    total = ref_lap.get("lap_duration")
    if s1 and s2 and total and float(total) > 0:
        race_state.sector_fractions = [
            float(s1) / float(total),
            (float(s1) + float(s2)) / float(total),
        ]
        logger.info("Sector fractions: %s", race_state.sector_fractions)


async def _load_final_car_positions(laps: list[dict]) -> None:
    """
    For finished races, fetch car positions at the moment the last driver
    crossed the finish line. We compute that moment from laps data
    (max of date_start + lap_duration across all valid final laps), which is
    far more accurate than using the session's date_end timestamp.
    """
    finish_times = []
    for lap in laps:
        if lap.get("date_start") and lap.get("lap_duration") and not lap.get("is_deleted"):
            start  = parse_dt(lap["date_start"])
            finish = start + timedelta(seconds=float(lap["lap_duration"]))
            finish_times.append(finish)

    if not finish_times:
        logger.warning("No lap finish times found — cannot determine race end for map.")
        return

    last_finish = max(finish_times)
    date_gte    = (last_finish - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_lte    = (last_finish + timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("Fetching final car positions around %s", last_finish.isoformat())

    final_locs = await openf1_client.get_locations(
        race_state.session_key, date_gte=date_gte, date_lte=date_lte
    )
    if final_locs:
        race_state.car_positions = build_car_positions(final_locs, race_state.drivers)
        logger.info("Final car positions loaded: %d drivers.", len(race_state.car_positions))
    else:
        logger.warning("No location data found around race finish — map will show no drivers.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    broadcaster.set_loop(asyncio.get_running_loop())

    session, is_live = await resolve_race_session()
    if not session:
        logger.warning("No valid race session found — API will return empty state.")
    else:
        race_state.session_key  = session["session_key"]
        race_state.meeting_key  = session["meeting_key"]
        race_state.session_type = session.get("session_name", "Race")
        race_state.is_live      = is_live

        # Round 1: meeting info + driver list (parallel, both need session/meeting key)
        meeting, drivers = await asyncio.gather(
            openf1_client.get_meeting(session["meeting_key"]),
            openf1_client.get_drivers(session["session_key"]),
        )
        if meeting:
            race_state.meeting_name = meeting.get("meeting_name")
        race_state.drivers = build_driver_map(drivers)

        # Round 2: all race data feeds (parallel)
        raw_positions, intervals, stints, laps = await asyncio.gather(
            openf1_client.get_positions(session["session_key"]),
            openf1_client.get_intervals(session["session_key"]),
            openf1_client.get_stints(session["session_key"]),
            openf1_client.get_laps(session["session_key"]),
        )

        race_state.normalized_positions = normalize_positions(raw_positions, race_state.drivers)
        race_state.intervals = intervals
        race_state.stints    = stints

        if laps:
            valid_laps = [l for l in laps if not l.get("is_deleted")]
            if valid_laps:
                race_state.lap_number = max(l["lap_number"] for l in valid_laps)
                if race_state.session_type in ("Race", "Sprint"):
                    race_state.total_laps = race_state.lap_number
            race_state.sectors_by_driver = build_latest_sectors(laps)

        race_state.last_updated = datetime.now(timezone.utc)

        # Heavy/slow data fetched in background so startup doesn't block the API.
        async def _load_background():
            try:
                tasks = [
                    _load_track_outline(session["session_key"], laps),
                ]
                if not is_live:
                    tasks.append(_load_final_car_positions(laps))
                await asyncio.gather(*tasks)
                logger.info("Map data fully loaded.")

                # Weather + race control + pit stops are owned by FastF1 for live
                # sessions; fetching from OpenF1 here would overwrite fresher data.
                if not is_live:
                    weather, race_control, pit_stops = await asyncio.gather(
                        openf1_client.get_weather(session["session_key"]),
                        openf1_client.get_race_control(session["session_key"]),
                        openf1_client.get_pit_stops(session["session_key"]),
                    )
                    if weather:
                        race_state.weather = latest_weather(weather)
                    race_state.race_control = race_control
                    race_state.pit_stops = pit_stops
                    logger.info(
                        "Weather + race control loaded (%d messages).", len(race_control)
                    )
                # Push updated state to any already-connected WS clients
                broadcaster.push()
            except Exception:
                logger.exception("Background data fetch failed.")

        asyncio.create_task(_load_background())

        if is_live:
            await start_live_timing()
            logger.info("Live race detected: %s — FastF1 live timing started.", race_state.meeting_name)
        else:
            logger.info("No live race. Showing last finished race: %s", race_state.meeting_name)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    race_state.is_live = False
    await openf1_client.close()
    logger.info("OpenF1 HTTP client closed.")


app = FastAPI(title="F1 Live Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(race_router)

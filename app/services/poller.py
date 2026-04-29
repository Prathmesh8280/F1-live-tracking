import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.state import race_state
from app.services.openf1_client import openf1_client
from app.services.sector_builder import build_latest_sectors
from app.services.position_builder import normalize_positions
from app.services.map_builder import build_car_positions
from app.services.weather_builder import latest_weather

logger = logging.getLogger(__name__)


async def poll_live_race():
    # Tick counter (each tick = 2s):
    #   Every tick  (2s):  positions, intervals, locations
    #   tick % 5 == 0 (10s): + stints, laps
    #   tick % 3 == 0 (6s):  + race control  (flags/safety car are time-sensitive)
    #   tick % 150 == 0 (300s / 5min): + weather
    tick = 0

    while race_state.is_live:
        try:
            session_key = race_state.session_key
            recent = (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            fetch_slow   = tick % 5  == 0  # stints + laps
            fetch_rc     = tick % 3  == 0  # race control
            fetch_weather = tick % 150 == 0  # weather — every 5 min

            coros = [
                openf1_client.get_positions(session_key),
                openf1_client.get_intervals(session_key),
                openf1_client.get_locations(session_key, date_gte=recent),
            ]
            if fetch_slow:
                coros += [openf1_client.get_stints(session_key), openf1_client.get_laps(session_key)]
            if fetch_rc:
                coros.append(openf1_client.get_race_control(session_key))
            if fetch_weather:
                coros.append(openf1_client.get_weather(session_key))

            results = await asyncio.gather(*coros)
            idx = 0

            raw_positions, intervals, locations = results[0], results[1], results[2]
            idx = 3

            if fetch_slow:
                stints, laps = results[idx], results[idx + 1]
                idx += 2
                race_state.stints = stints
                if laps:
                    valid_laps = [l for l in laps if not l.get("is_deleted")]
                    if valid_laps:
                        race_state.lap_number = max(l["lap_number"] for l in valid_laps)
                    race_state.sectors_by_driver = build_latest_sectors(laps)

            if fetch_rc:
                race_state.race_control = results[idx]
                idx += 1

            if fetch_weather:
                weather = results[idx]
                if weather:
                    race_state.weather = latest_weather(weather)

            race_state.normalized_positions = normalize_positions(raw_positions, race_state.drivers)
            race_state.intervals = intervals
            if locations:
                race_state.car_positions = build_car_positions(locations, race_state.drivers)

            race_state.last_updated = datetime.now(timezone.utc)
            tick += 1

        except Exception:
            logger.exception("Polling error — will retry in 2 s")

        await asyncio.sleep(2)

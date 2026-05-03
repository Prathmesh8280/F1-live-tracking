import asyncio
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone

from app.core.state import race_state
from app.services.broadcaster import broadcaster

logger = logging.getLogger(__name__)

_SESSION_PRIORITY = [
    "Race", "Qualifying", "Sprint", "Sprint Qualifying",
    "Practice 3", "Practice 2", "Practice 1",
]


async def load_last_session() -> bool:
    """
    Load the most recent completed F1 session via FastF1 historical API.
    Runs the blocking FastF1 call in a thread executor so the event loop stays free.
    Returns True if data was loaded and pushed to race_state.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_load)


def _sync_load() -> bool:
    try:
        import fastf1
        import pandas as pd

        cache_dir = os.path.join(tempfile.gettempdir(), "f1_cache")
        os.makedirs(cache_dir, exist_ok=True)
        fastf1.Cache.enable_cache(cache_dir)

        year = datetime.now().year
        session = _find_latest_session(fastf1, pd, year)
        if session is None and year > 2018:
            session = _find_latest_session(fastf1, pd, year - 1)

        if session is None:
            logger.warning("No completed session found in FastF1 schedule")
            return False

        _populate_state(session)
        # Load telemetry (track outline + pitlane) in a background thread so
        # the initial timing/results data is pushed to clients right away.
        t = threading.Thread(
            target=_load_track_outline_background,
            args=(session,),
            daemon=True,
            name="f1-telemetry-load",
        )
        t.start()
        return True

    except Exception:
        logger.exception("Historical session load failed")
        return False


def _find_latest_session(fastf1, pd, year: int):
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
    except Exception as e:
        logger.warning("Could not fetch %d schedule: %s", year, e)
        return None

    now = pd.Timestamp.now(tz="UTC")

    # EventDate is the race day — use it to find past events
    try:
        dates = pd.to_datetime(schedule["EventDate"], utc=True)
    except Exception:
        dates = pd.to_datetime(schedule["EventDate"])

    past = schedule[dates < now]
    if past.empty:
        return None

    last_event = past.iloc[-1]
    round_num = int(last_event["RoundNumber"])
    logger.info("Loading last event: Round %d %s %d", round_num, last_event.get("EventName", ""), year)

    for sess_name in _SESSION_PRIORITY:
        try:
            session = fastf1.get_session(year, round_num, sess_name)
            # Phase 1: fast load without telemetry — gets timing/weather/messages
            session.load(laps=True, telemetry=False, weather=True, messages=True)
            has_results = hasattr(session, "results") and not session.results.empty
            if not has_results:
                continue
            logger.info("Found session: %s %s", last_event.get("EventName", ""), sess_name)
            return session
        except Exception as e:
            logger.debug("Session %s/%d/%s not available: %s", year, round_num, sess_name, e)
            continue

    return None


def _populate_state(session) -> None:
    import pandas as pd

    # ── Session metadata ──────────────────────────────────────────────
    race_state.meeting_name = (
        session.event.get("OfficialEventName")
        or session.event.get("EventName", "")
    )
    race_state.session_type = session.name
    race_state.is_live = False

    # ── Drivers + standings from results ─────────────────────────────
    if hasattr(session, "results") and not session.results.empty:
        drivers = {}
        positions = []
        for _, row in session.results.iterrows():
            try:
                num = int(row["DriverNumber"])
            except (ValueError, TypeError):
                continue
            color = str(row.get("TeamColor", "") or "")
            if color and not color.startswith("#"):
                color = f"#{color}"
            driver = {
                "number":     num,
                "code":       str(row.get("Abbreviation", f"#{num}")),
                "full_name":  str(row.get("FullName", "")),
                "team_name":  str(row.get("TeamName", "")),
                "team_color": color or "#555555",
            }
            drivers[num] = driver
            try:
                pos = int(row["Position"])
            except (ValueError, TypeError):
                pos = 999
            positions.append({"position": pos, "driver": driver})

        race_state.drivers = drivers
        race_state.normalized_positions = sorted(positions, key=lambda r: r["position"])

    # ── Best sector + lap times per driver ────────────────────────────
    if not session.laps.empty:
        sectors = {}
        for num_str, driver_laps in session.laps.groupby("DriverNumber"):
            try:
                num = int(num_str)
            except (ValueError, TypeError):
                continue
            valid = driver_laps[driver_laps["LapTime"].notna()]
            if valid.empty:
                continue
            best = valid.loc[valid["LapTime"].idxmin()]
            sectors[num] = {
                "sector_1":      _td(best.get("Sector1Time")),
                "sector_2":      _td(best.get("Sector2Time")),
                "sector_3":      _td(best.get("Sector3Time")),
                "best_sector_1": _td(best.get("Sector1Time")),
                "best_sector_2": _td(best.get("Sector2Time")),
                "best_sector_3": _td(best.get("Sector3Time")),
                "lap_time":      _td(best.get("LapTime")),
                "best_lap_time": _td(best.get("LapTime")),
                "lap_number":    int(best.get("LapNumber", 0)),
            }
        race_state.sectors_by_driver = sectors

    # ── Tyre stints ───────────────────────────────────────────────────
    if not session.laps.empty and "Compound" in session.laps.columns:
        stints = _build_stints(session.laps)
        race_state.stints = stints

    # ── Weather (last record) ─────────────────────────────────────────
    if hasattr(session, "weather_data") and not session.weather_data.empty:
        w = session.weather_data.iloc[-1]
        race_state.weather = {
            "air_temp":       _f(w.get("AirTemp")),
            "track_temp":     _f(w.get("TrackTemp")),
            "humidity":       _f(w.get("Humidity")),
            "wind_speed":     _f(w.get("WindSpeed")),
            "wind_direction": _f(w.get("WindDirection")),
            "rainfall":       bool(w.get("Rainfall", False)),
        }

    # ── Race control messages ─────────────────────────────────────────
    if hasattr(session, "race_control_messages") and not session.race_control_messages.empty:
        msgs = []
        for _, msg in session.race_control_messages.iterrows():
            t = msg.get("Time")
            date_str = t.isoformat() if hasattr(t, "isoformat") else str(t)
            msgs.append({
                "date":       date_str,
                "flag":       str(msg.get("Flag", "")),
                "message":    str(msg.get("Message", "")),
                "scope":      str(msg.get("Scope", "")),
                "category":   str(msg.get("Category", "")),
                "lap_number": msg.get("RacingNumber"),
            })
        race_state.race_control = msgs

    race_state.last_updated = datetime.now(timezone.utc)
    broadcaster.push()
    logger.info(
        "Historical data loaded: %s — %s (%d drivers, %d sector entries)",
        race_state.meeting_name,
        race_state.session_type,
        len(race_state.drivers),
        len(race_state.sectors_by_driver),
    )


def _load_track_outline_background(session) -> None:
    """Re-load session with telemetry to extract GPS track outline and pitlane."""
    try:
        import fastf1
        year = session.date.year
        round_num = int(session.event["RoundNumber"])
        sess_name = session.name

        tel_session = fastf1.get_session(year, round_num, sess_name)
        tel_session.load(laps=True, telemetry=True, weather=False, messages=False)

        if tel_session.laps.empty:
            return

        # Track outline from fastest flying lap
        fastest = tel_session.laps.pick_fastest()
        tel = fastest.get_telemetry()
        if "X" in tel.columns and "Y" in tel.columns and len(tel) >= 10:
            step = max(1, len(tel) // 600)
            race_state.track_outline = [
                {"x": float(x), "y": float(y)}
                for x, y in zip(tel["X"].values[::step], tel["Y"].values[::step])
            ]
            logger.info("Track outline: %d points", len(race_state.track_outline))

        # Pitlane from a lap where the car pitted in
        _extract_pitlane(tel_session)

        # For Race sessions: place cars at their position when the last car finishes
        if sess_name == "Race" and race_state.track_outline:
            car_pos = _compute_race_end_positions(
                tel_session.laps, race_state.track_outline, race_state.drivers
            )
            if car_pos:
                race_state.car_positions = car_pos
                logger.info("Race end positions computed: %d drivers", len(car_pos))

        broadcaster.push()
    except Exception as e:
        logger.warning("Track outline telemetry load skipped: %s", e)


def _extract_pitlane(session) -> None:
    """Extract pitlane GPS coordinates from a pit-in lap's telemetry."""
    try:
        pit_laps = session.laps[session.laps["PitInTime"].notna()]
        if pit_laps.empty:
            pit_laps = session.laps[session.laps["PitOutTime"].notna()]
        if pit_laps.empty:
            logger.info("Pitlane: no pit laps found in session")
            return

        logger.info("Pitlane: found %d pit laps to try", len(pit_laps))

        for _, lap in pit_laps.iterrows():
            try:
                tel = lap.get_telemetry()
                if "X" not in tel.columns or "Y" not in tel.columns:
                    continue

                logger.info("Pitlane telemetry columns: %s", list(tel.columns))
                pit_tel = None

                # Option 1: InPit boolean/int column
                if "InPit" in tel.columns:
                    mask = tel["InPit"].astype(bool)
                    if mask.any():
                        pit_tel = tel[mask]
                        logger.info("Pitlane via InPit: %d points", len(pit_tel))

                # Option 2: Status column (FastF1 marks pitlane as non-OnTrack)
                if (pit_tel is None or len(pit_tel) < 5) and "Status" in tel.columns:
                    unique_statuses = tel["Status"].unique().tolist()
                    logger.info("Pitlane Status values: %s", unique_statuses)
                    mask = tel["Status"] != "OnTrack"
                    if mask.any():
                        pit_tel = tel[mask]
                        logger.info("Pitlane via Status: %d points", len(pit_tel))

                # Option 3: Speed fallback — slow section at end of pit-in lap
                if (pit_tel is None or len(pit_tel) < 5) and "Speed" in tel.columns:
                    n = len(tel)
                    tail = tel.iloc[int(n * 0.65):]
                    slow = tail[tail["Speed"] < 100]
                    if len(slow) >= 5:
                        pit_tel = slow
                        logger.info("Pitlane via speed fallback: %d points", len(pit_tel))

                if pit_tel is None or len(pit_tel) < 5:
                    continue

                step = max(1, len(pit_tel) // 150)
                race_state.pitlane_outline = [
                    {"x": float(x), "y": float(y)}
                    for x, y in zip(pit_tel["X"].values[::step], pit_tel["Y"].values[::step])
                ]
                logger.info("Pitlane outline set: %d points", len(race_state.pitlane_outline))
                return

            except Exception as e:
                logger.warning("Pit lap telemetry error: %s", e)
                continue

        logger.warning("Pitlane: could not extract from any pit lap")
    except Exception as e:
        logger.warning("Pitlane extraction failed: %s", e)


def _compute_race_end_positions(laps, outline: list, drivers: dict) -> dict:
    """
    Place each driver at their position on the cool-down lap at the moment
    the last classified finisher crosses the start/finish line.

    The last finisher sits at outline[0] (start/finish). Every driver who
    finished earlier has been on their cool-down lap longer, so they appear
    proportionally further around the circuit. We estimate the cool-down lap
    duration as 1.5× the session's fastest lap time.
    """
    import pandas as pd

    if laps.empty or not outline:
        return {}

    n = len(outline)

    # Build a map of driver_number → time they crossed the finish line
    # (end of their last complete racing lap)
    finish_times = {}
    for num_str, driver_laps in laps.groupby("DriverNumber"):
        try:
            num = int(num_str)
        except (ValueError, TypeError):
            continue
        valid = driver_laps[driver_laps["LapTime"].notna()].sort_values("LapNumber")
        if valid.empty:
            continue
        last_lap = valid.iloc[-1]
        t_start = last_lap.get("LapStartDate")
        t_lap   = last_lap.get("LapTime")
        if pd.isna(t_start) or pd.isna(t_lap):
            continue
        finish_times[num] = t_start + t_lap

    if not finish_times:
        return {}

    t_last = max(finish_times.values())

    # Estimate cool-down lap time as 1.5× the fastest recorded lap
    try:
        best_s     = laps["LapTime"].dropna().min().total_seconds()
        cooldown_s = max(best_s * 1.5, 90.0)
    except Exception:
        cooldown_s = 120.0

    result = {}
    for num, t_finish in finish_times.items():
        driver   = drivers.get(num, {})
        delta_s  = (t_last - t_finish).total_seconds()
        fraction = min(delta_s / cooldown_s, 0.97)   # cap so no one wraps past S/F
        idx      = int(fraction * n)
        pt       = outline[idx]
        result[num] = {
            "x":          pt["x"],
            "y":          pt["y"],
            "code":       driver.get("code", f"#{num}"),
            "team_color": driver.get("team_color", "#888"),
        }

    logger.info(
        "Race end positions: %d drivers placed, last finish=%s, cooldown=%.0fs",
        len(result), t_last, cooldown_s,
    )
    return result


def _build_stints(laps) -> list:
    stints = []
    for num_str, driver_laps in laps.groupby("DriverNumber"):
        try:
            num = int(num_str)
        except (ValueError, TypeError):
            continue
        driver_laps = driver_laps.sort_values("LapNumber")
        stint_num = 0
        prev_compound = None
        stint_start = None
        for _, lap in driver_laps.iterrows():
            compound = lap.get("Compound", "UNKNOWN") or "UNKNOWN"
            lap_num = int(lap.get("LapNumber", 0))
            if compound != prev_compound:
                if prev_compound is not None and stint_start is not None:
                    stints.append(_make_stint(num, stint_num, prev_compound, stint_start, lap_num - 1))
                stint_num += 1
                prev_compound = compound
                stint_start = lap_num
        if prev_compound and stint_start is not None:
            stints.append(_make_stint(num, stint_num, prev_compound, stint_start, None))
    return stints


def _make_stint(driver_num, idx, compound, lap_start, lap_end) -> dict:
    return {
        "driver_number": driver_num,
        "stint_number":  idx,
        "compound":      str(compound).upper(),
        "lap_start":     lap_start,
        "lap_end":       lap_end,
        "tyre_age_at_start": 0,
        "new_tyre":      True,
    }


def _td(value) -> float | None:
    if value is None:
        return None
    try:
        import pandas as pd
        if pd.isna(value):
            return None
        return float(value.total_seconds())
    except Exception:
        return None


def _f(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

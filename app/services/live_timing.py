import json
import logging
import os
import time
import zlib
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from fastf1.livetiming.client import SignalRClient

from app.core.state import race_state
from app.services.broadcaster import broadcaster

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="f1-live")

try:
    from signalrcore.messages.completion_message import CompletionMessage as _CompletionMsg
except ImportError:
    _CompletionMsg = type(None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decompress(data: str) -> Any:
    raw = zlib.decompress(base64.b64decode(data), -zlib.MAX_WBITS)
    return json.loads(raw)


def _deep_update(base: dict, update: dict) -> None:
    """Apply an incremental diff onto base in-place."""
    for key, val in update.items():
        if isinstance(val, dict) and key in base and isinstance(base[key], dict):
            _deep_update(base[key], val)
        else:
            base[key] = val


def _parse_time(value: str) -> float | None:
    """Convert '1:23.456' or '23.456' to seconds. Returns None on failure."""
    if not value:
        return None
    try:
        if ':' in value:
            m, s = value.split(':', 1)
            return int(m) * 60 + float(s)
        return float(value)
    except (ValueError, AttributeError):
        return None


# ── FastF1 client subclass ────────────────────────────────────────────────────

class _F1LiveClient(SignalRClient):
    """
    Thin subclass that intercepts _on_message before it can write to a file,
    routing each (topic, data) pair to LiveTimingService instead.
    """

    def __init__(self, service: "LiveTimingService"):
        # os.devnull satisfies the required filename param; we never actually
        # write to it because we fully override _on_message.
        super().__init__(filename=os.devnull)
        self._svc = service
        # Limit topics to what we actually use — reduces bandwidth
        self.topics = [
            "SessionInfo", "DriverList", "LapCount",
            "TimingData", "TimingAppData",
            "WeatherData", "RaceControlMessages",
            "ExtrapolatedClock",
            "Position.z",
        ]

    def _on_message(self, msg: list | _CompletionMsg) -> None:
        # Keep the timeout watchdog alive
        self._t_last_message = time.time()

        if isinstance(msg, _CompletionMsg) or not isinstance(msg, list) or len(msg) < 2:
            return
        topic, data = msg[0], msg[1]
        try:
            self._svc.handle(topic, data)
        except Exception:
            logger.exception("LiveTiming handler error on topic %s", topic)


# ── State service ─────────────────────────────────────────────────────────────

class LiveTimingService:
    """
    Receives incremental FastF1 feed messages and merges them into race_state.
    All topic data arrives as partial diffs — we maintain full local copies
    (_timing, _timing_app, _driver_list) and rebuild derived state after each.
    """

    def __init__(self):
        self._timing:      dict = {}   # merged TimingData.Lines state
        self._timing_app:  dict = {}   # merged TimingAppData.Lines state
        self._driver_list: dict = {}   # merged DriverList state
        self._rc_messages: list = []   # accumulated RaceControlMessages

    def reset(self) -> None:
        self._timing.clear()
        self._timing_app.clear()
        self._driver_list.clear()
        self._rc_messages.clear()

    # ── Topic handlers ────────────────────────────────────────────────

    def handle(self, topic: str, data: Any) -> None:
        dispatch = {
            "SessionInfo":         self._session_info,
            "DriverList":          self._driver_list_update,
            "LapCount":            self._lap_count,
            "TimingData":          self._timing_data,
            "TimingAppData":       self._timing_app_data,
            "WeatherData":         self._weather,
            "RaceControlMessages": self._race_control,
            "ExtrapolatedClock":   self._extrapolated_clock,
            "Position.z":          self._positions,
        }
        handler = dispatch.get(topic)
        if handler:
            handler(data)

    def _session_info(self, data: dict) -> None:
        meeting = data.get("Meeting", {})
        name = meeting.get("OfficialName") or meeting.get("Name", "")
        if name:
            race_state.meeting_name = name
        # FastF1 sends the session name ("Practice 1", "Qualifying", "Race", ...)
        # Use it to fill session_type when OpenF1 didn't seed it.
        session_name = data.get("Name", "")
        if session_name:
            race_state.session_type = session_name
        race_state.is_live = True
        broadcaster.push()

    def _driver_list_update(self, data: dict) -> None:
        _deep_update(self._driver_list, data)
        drivers = {}
        for num_str, info in self._driver_list.items():
            if not isinstance(info, dict):
                continue
            try:
                num = int(num_str)
            except ValueError:
                continue
            color = info.get("TeamColour", "")
            if color and not color.startswith("#"):
                color = f"#{color}"
            drivers[num] = {
                "number":     num,
                "code":       info.get("Tla", f"#{num}"),
                "full_name":  info.get("FullName", ""),
                "team_name":  info.get("TeamName", ""),
                "team_color": color or "#555555",
            }
        if drivers:
            race_state.drivers = drivers
            self._rebuild_positions()
            broadcaster.push()

    def _lap_count(self, data: dict) -> None:
        try:
            race_state.lap_number = int(data["CurrentLap"])
        except (KeyError, ValueError, TypeError):
            pass
        try:
            race_state.total_laps = int(data["TotalLaps"])
        except (KeyError, ValueError, TypeError):
            pass
        broadcaster.push()

    def _timing_data(self, data: dict) -> None:
        lines = data.get("Lines", {})
        if not lines:
            return
        _deep_update(self._timing, lines)
        self._rebuild_positions()
        self._rebuild_intervals()
        self._rebuild_sectors()
        self._rebuild_pit_stops()
        race_state.last_updated = datetime.now(timezone.utc)
        broadcaster.push()

    def _timing_app_data(self, data: dict) -> None:
        lines = data.get("Lines", {})
        if not lines:
            return
        _deep_update(self._timing_app, lines)
        self._rebuild_stints()
        broadcaster.push()

    def _weather(self, data: dict) -> None:
        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        race_state.weather = {
            "air_temp":       _f(data.get("AirTemp")),
            "track_temp":     _f(data.get("TrackTemp")),
            "humidity":       _f(data.get("Humidity")),
            "wind_speed":     _f(data.get("WindSpeed")),
            "wind_direction": _f(data.get("WindDirection")),
            "rainfall":       data.get("Rainfall", "0") not in ("0", "", None, False, 0),
        }
        broadcaster.push()

    def _race_control(self, data: dict) -> None:
        messages = data.get("Messages", {})
        if isinstance(messages, dict):
            messages = list(messages.values())
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            self._rc_messages.append({
                "date":       msg.get("Utc", ""),
                "flag":       msg.get("Flag", ""),
                "message":    msg.get("Message", ""),
                "scope":      msg.get("Scope", ""),
                "category":   msg.get("Category", ""),
                "lap_number": msg.get("Lap"),
            })
        race_state.race_control = list(self._rc_messages)
        broadcaster.push()

    def _extrapolated_clock(self, data: dict) -> None:
        remaining = data.get("Remaining", "")
        if remaining:
            race_state.session_remaining = remaining.split(".")[0]
            broadcaster.push()

    def _positions(self, data: str | dict) -> None:
        try:
            raw = _decompress(data) if isinstance(data, str) else data
            entries_list = raw.get("Position", [])
            if not entries_list:
                return
            latest = entries_list[-1].get("Entries", {})
            car_positions = {}
            for num_str, coords in latest.items():
                try:
                    num = int(num_str)
                except ValueError:
                    continue
                driver = race_state.drivers.get(num, {})
                car_positions[num] = {
                    "x":          coords.get("X", 0),
                    "y":          coords.get("Y", 0),
                    "code":       driver.get("code", f"#{num}"),
                    "team_color": driver.get("team_color", "#888"),
                }
            race_state.car_positions = car_positions
        except Exception:
            logger.debug("Position.z decode failed — skipping frame")

    # ── State rebuilders ──────────────────────────────────────────────

    def _rebuild_positions(self) -> None:
        drivers = race_state.drivers
        rows = []
        for num_str, td in self._timing.items():
            if not isinstance(td, dict):
                continue
            try:
                num = int(num_str)
                pos = int(td.get("Position", 999))
            except (ValueError, TypeError):
                continue
            driver = drivers.get(num, {"number": num, "code": f"#{num}", "team_color": "#555"})
            rows.append({"position": pos, "driver": driver})
        rows.sort(key=lambda r: r["position"])
        race_state.normalized_positions = rows

    def _rebuild_intervals(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        intervals = []
        for num_str, td in self._timing.items():
            if not isinstance(td, dict):
                continue
            try:
                num = int(num_str)
            except ValueError:
                continue
            gap     = td.get("GapToLeader", "")
            int_raw = td.get("IntervalToPositionAhead", {})
            int_val = int_raw.get("Value", "") if isinstance(int_raw, dict) else str(int_raw)
            intervals.append({
                "driver_number": num,
                "gap_to_leader": gap,
                "interval":      int_val,
                "date":          now,
            })
        race_state.intervals = intervals

    def _rebuild_sectors(self) -> None:
        sectors = {}
        for num_str, td in self._timing.items():
            if not isinstance(td, dict):
                continue
            try:
                num = int(num_str)
            except ValueError:
                continue
            raw_s = td.get("Sectors", {})

            def _sv(k):
                s = raw_s.get(str(k), {})
                if not isinstance(s, dict):
                    return None, None
                return _parse_time(s.get("Value", "")), _parse_time(s.get("PreviousValue", ""))

            s1, b1 = _sv(0)
            s2, b2 = _sv(1)
            s3, b3 = _sv(2)

            last_raw = td.get("LastLapTime", {})
            best_raw = td.get("BestLapTime", {})
            last_v = last_raw.get("Value", "") if isinstance(last_raw, dict) else ""
            best_v = best_raw.get("Value", "") if isinstance(best_raw, dict) else ""

            sectors[num] = {
                "sector_1":      s1,
                "sector_2":      s2,
                "sector_3":      s3,
                "best_sector_1": b1,
                "best_sector_2": b2,
                "best_sector_3": b3,
                "lap_time":      _parse_time(last_v),
                "best_lap_time": _parse_time(best_v),
                "lap_number":    race_state.lap_number,
            }
        race_state.sectors_by_driver = sectors

    def _rebuild_pit_stops(self) -> None:
        pit_stops = []
        for num_str, td in self._timing.items():
            if not isinstance(td, dict):
                continue
            if td.get("InPit"):
                try:
                    num = int(num_str)
                except ValueError:
                    continue
                pit_stops.append({
                    "driver_number": num,
                    "lap_number":    race_state.lap_number,
                    "pit_duration":  None,
                })
        race_state.pit_stops = pit_stops

    def _rebuild_stints(self) -> None:
        stints = []
        for num_str, app in self._timing_app.items():
            if not isinstance(app, dict):
                continue
            try:
                num = int(num_str)
            except ValueError:
                continue
            raw_stints = app.get("Stints", {})
            if not isinstance(raw_stints, dict):
                continue
            for idx_str, stint in raw_stints.items():
                if not isinstance(stint, dict):
                    continue
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                total = stint.get("TotalLaps", 0)
                start = stint.get("StartLaps", 0)
                stints.append({
                    "driver_number":     num,
                    "stint_number":      idx + 1,
                    "compound":          stint.get("Compound", "UNKNOWN"),
                    "lap_start":         start,
                    "lap_end":           (start + total) if total else None,
                    "tyre_age_at_start": start,
                    "new_tyre":          stint.get("New", "true") == "true",
                })
        race_state.stints = stints


# ── Public entry point ────────────────────────────────────────────────────────

_service = LiveTimingService()


async def start_live_timing() -> None:
    """
    Spawn the FastF1 SignalR client in a background thread.
    Non-blocking: returns immediately while the thread runs.
    """
    import asyncio

    _service.reset()
    client = _F1LiveClient(_service)
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_executor, client.start)

    def _done(fut):
        exc = fut.exception()
        if exc:
            logger.error("FastF1 live timing client exited with error: %s", exc)
        else:
            logger.info("FastF1 live timing client exited cleanly.")
        race_state.is_live = False

    future.add_done_callback(_done)
    logger.info("FastF1 live timing thread started.")

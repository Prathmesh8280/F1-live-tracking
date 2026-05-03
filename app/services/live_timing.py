import asyncio
import json
import logging
import os
import threading
import time
import zlib
import base64
from datetime import datetime, timezone
from typing import Any

from fastf1.livetiming.client import SignalRClient
from signalrcore.messages.completion_message import CompletionMessage

from app.core.state import race_state
from app.services.broadcaster import broadcaster


logger = logging.getLogger(__name__)


async def _fetch_circuit_from_fastf1(session_path: str) -> None:
    """
    Load a 2025 session for the same circuit via FastF1 historical API and
    extract GPS telemetry from the fastest lap to build the circuit outline.
    """
    import tempfile

    # session_path e.g. "2026/2026-05-03_Miami_Grand_Prix/2026-05-01_Practice_1/"
    # meeting_part = "2026-05-03_Miami_Grand_Prix"
    # split("_") → ["2026-05-03", "Miami", "Grand", "Prix"]
    # [1:] skips the hyphen-date token → ["Miami", "Grand", "Prix"]
    # strip "Grand Prix" → "Miami"
    parts = session_path.strip("/").split("/")
    meeting_part = parts[1] if len(parts) > 1 else ""
    words = meeting_part.split("_")[1:]
    location = " ".join(words).replace("Grand Prix", "").replace("Grand", "").strip()
    if not location:
        logger.warning("Cannot parse location from session path: %s", session_path)
        return

    logger.info("Fetching 2025 FastF1 historical session for circuit: %r", location)

    def _load_sync():
        try:
            import fastf1
            cache_dir = os.path.join(tempfile.gettempdir(), "f1_circuit_cache")
            os.makedirs(cache_dir, exist_ok=True)
            fastf1.Cache.enable_cache(cache_dir)

            session = fastf1.get_session(2025, location, "FP1")
            logger.info(
                "FastF1 matched: %s at %s",
                session.event.get("EventName", "?"),
                session.event.get("Location", "?"),
            )
            session.load(laps=True, telemetry=True, weather=False, messages=False)

            if session.laps.empty:
                return None
            fastest = session.laps.pick_fastest()
            tel = fastest.get_telemetry()
            if "X" not in tel.columns or "Y" not in tel.columns:
                return None

            step = max(1, len(tel) // 600)
            outline = [
                {"x": float(x), "y": float(y)}
                for x, y in zip(tel["X"].values[::step], tel["Y"].values[::step])
            ]

            # Extract pitlane from a pit-in lap (three fallback strategies)
            pitlane = []
            try:
                pit_laps = session.laps[session.laps["PitInTime"].notna()]
                if pit_laps.empty:
                    pit_laps = session.laps[session.laps["PitOutTime"].notna()]
                for _, lap in pit_laps.iterrows():
                    p_tel = lap.get_telemetry()
                    if "X" not in p_tel.columns or "Y" not in p_tel.columns:
                        continue
                    pit_tel = None
                    if "InPit" in p_tel.columns:
                        mask = p_tel["InPit"].astype(bool)
                        if mask.any():
                            pit_tel = p_tel[mask]
                    if (pit_tel is None or len(pit_tel) < 5) and "Status" in p_tel.columns:
                        mask = p_tel["Status"] != "OnTrack"
                        if mask.any():
                            pit_tel = p_tel[mask]
                    if (pit_tel is None or len(pit_tel) < 5) and "Speed" in p_tel.columns:
                        n = len(p_tel)
                        tail = p_tel.iloc[int(n * 0.65):]
                        slow = tail[tail["Speed"] < 100]
                        if len(slow) >= 5:
                            pit_tel = slow
                    if pit_tel is None or len(pit_tel) < 5:
                        continue
                    s = max(1, len(pit_tel) // 150)
                    pitlane = [
                        {"x": float(x), "y": float(y)}
                        for x, y in zip(pit_tel["X"].values[::s], pit_tel["Y"].values[::s])
                    ]
                    logger.info("Circuit pitlane: %d points extracted", len(pitlane))
                    break
            except Exception as exc:
                logger.warning("Pitlane extraction error: %s", exc)

            return outline, pitlane
        except Exception as exc:
            logger.warning("FastF1 historical load error: %s", exc)
            return None

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _load_sync)
    if result:
        outline, pitlane = result
        race_state.track_outline = outline
        if pitlane:
            race_state.pitlane_outline = pitlane
            logger.info("Pitlane outline: %d points", len(pitlane))
        logger.info("Circuit outline from FastF1 historical: %d points", len(outline))
        broadcaster.push()
    else:
        logger.warning("FastF1 historical load failed — no circuit outline available")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decompress(data: str) -> Any:
    raw = zlib.decompress(base64.b64decode(data), -zlib.MAX_WBITS)
    return json.loads(raw)


def _deep_update(base: dict, update: dict) -> None:
    """Apply an incremental diff onto base in-place."""
    for key, val in update.items():
        if isinstance(val, dict) and key in base and isinstance(base[key], dict):
            _deep_update(base[key], val)
        elif isinstance(val, list) and key in base and isinstance(base[key], list):
            # Merge list elements positionally: only update indices present in val
            for i, item in enumerate(val):
                if i < len(base[key]) and isinstance(item, dict) and isinstance(base[key][i], dict):
                    _deep_update(base[key][i], item)
                elif i < len(base[key]):
                    base[key][i] = item
                else:
                    base[key].append(item)
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

_PRIORITY = {
    "SessionInfo": 0, "SessionStatus": 1, "DriverList": 2,
    "TimingAppData": 3, "TimingData": 4,
    "WeatherData": 5, "RaceControlMessages": 6, "ExtrapolatedClock": 7,
}


class _F1LiveClient(SignalRClient):
    """
    Subclass of FastF1's SignalRClient that routes messages to LiveTimingService
    instead of writing them to a file.

    FastF1 3.8.3 uses SignalR Core (wss://livetiming.formula1.com/signalrcore).
    _on_message receives either:
      - CompletionMessage  — the initial full-state snapshot from Subscribe
      - list               — incremental feed update: [topic, data, ...]
    """

    def __init__(self, service: "LiveTimingService"):
        super().__init__(filename=os.devnull, timeout=0, no_auth=True)
        self._svc = service
        self.topics = [
            "SessionInfo", "SessionStatus", "DriverList", "LapCount",
            "TimingData", "TimingAppData",
            "WeatherData", "RaceControlMessages",
            "ExtrapolatedClock", "TrackStatus",
            "Position.z",
        ]

    def _run(self) -> None:
        """Override _run to omit access_token_factory entirely (signalrcore
        rejects None; FastF1 passes None when no_auth=True)."""
        import requests
        from signalrcore.hub_connection_builder import HubConnectionBuilder

        self._output_file = open(self.filename, self.filemode)

        try:
            r = requests.options(self._negotiate_url, headers=self.headers)
            cookie = r.cookies.get("AWSALBCORS")
            if cookie:
                self.headers.update({"Cookie": f"AWSALBCORS={cookie}"})
        except Exception as e:
            logger.warning("SignalR pre-negotiate failed: %s — continuing without cookie", e)

        self._connection = (
            HubConnectionBuilder()
            .with_url(self._connection_url, options={
                "verify_ssl": True,
                "headers": self.headers,
            })
            .configure_logging(logging.WARNING)
            .build()
        )

        self._connection.on_open(self._on_connect)
        self._connection.on_close(self._on_close)
        self._connection.on("feed", self._on_message)
        self._connection.start()

        while not self._is_connected:
            time.sleep(0.1)

        self._connection.send("Subscribe", [self.topics], on_invocation=self._on_message)

    def _on_message(self, msg: list | CompletionMessage) -> None:
        self._t_last_message = time.time()

        if isinstance(msg, CompletionMessage):
            # Initial snapshot: msg.result is {topic: data, ...}
            if not isinstance(msg.result, dict):
                return
            ordered = sorted(
                msg.result.items(),
                key=lambda kv: _PRIORITY.get(kv[0], 99),
            )
            for topic, topic_data in ordered:
                if topic_data:
                    try:
                        self._svc.handle(topic, topic_data)
                    except Exception:
                        logger.exception("Initial state error on topic %s", topic)

        elif isinstance(msg, list) and len(msg) >= 2:
            topic, data = msg[0], msg[1]
            try:
                self._svc.handle(topic, data)
            except Exception:
                logger.exception("Feed handler error on topic %s", topic)


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
        self._best_sectors: dict = {}  # driver_num -> {s1, s2, s3} rolling minimums

    def reset(self) -> None:
        self._timing.clear()
        self._timing_app.clear()
        self._driver_list.clear()
        self._rc_messages.clear()
        self._best_sectors.clear()
        race_state.car_positions = {}

    # ── Topic handlers ────────────────────────────────────────────────

    def handle(self, topic: str, data: Any) -> None:
        dispatch = {
            "SessionInfo":         self._session_info,
            "SessionStatus":       self._session_status,
            "DriverList":          self._driver_list_update,
            "LapCount":            self._lap_count,
            "TimingData":          self._timing_data,
            "TimingAppData":       self._timing_app_data,
            "WeatherData":         self._weather,
            "RaceControlMessages": self._race_control,
            "ExtrapolatedClock":   self._extrapolated_clock,
            "TrackStatus":         self._track_status,
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
        session_name = data.get("Name", "")
        if session_name:
            race_state.session_type = session_name
        key = data.get("Key")
        if key and not race_state.session_key:
            try:
                race_state.session_key = int(key)
                logger.info("Session key from FastF1: %d", race_state.session_key)
            except (ValueError, TypeError):
                pass
        # SessionStatus inside SessionInfo dict (initial state snapshot)
        status = data.get("SessionStatus", {})
        if isinstance(status, dict):
            status = status.get("Status", "")
        self._apply_session_status(str(status))

        broadcaster.push()

        # Build circuit outline from FastF1 historical data (runs in background thread)
        if not race_state.track_outline and broadcaster._loop:
            session_path = data.get("Path", "")
            if session_path:
                asyncio.run_coroutine_threadsafe(
                    _fetch_circuit_from_fastf1(session_path),
                    broadcaster._loop,
                )

    _INACTIVE_STATUSES = {"Finalised", "Finished", "Ends", "Aborted", "Inactive"}

    def _apply_session_status(self, status: str) -> None:
        if not status:
            return
        if status in self._INACTIVE_STATUSES:
            race_state.is_live = False
        else:
            race_state.is_live = True

    def _session_status(self, data: Any) -> None:
        # Arrives as a plain string or {"Status": "..."} dict
        if isinstance(data, dict):
            status = data.get("Status", "")
        else:
            status = str(data)
        self._apply_session_status(status)
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
        # Normalize stints to dict immediately. The initial snapshot sends stints
        # as a list; incremental updates send a partial dict (e.g. just TotalLaps).
        # If we leave the list in place, _deep_update replaces it wholesale with
        # the partial dict and the Compound field is lost → shows "?".
        for driver_data in self._timing_app.values():
            if isinstance(driver_data, dict):
                raw = driver_data.get("Stints")
                if isinstance(raw, list):
                    driver_data["Stints"] = {str(i): s for i, s in enumerate(raw)}
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
        if len(self._rc_messages) > 200:
            self._rc_messages = self._rc_messages[-200:]
        race_state.race_control = list(self._rc_messages)
        broadcaster.push()

    def _extrapolated_clock(self, data: dict) -> None:
        remaining = data.get("Remaining", "")
        if remaining:
            race_state.session_remaining = remaining.split(".")[0]
            broadcaster.push()

    def _track_status(self, data: Any) -> None:
        # Codes: 1=Clear, 2=Yellow, 4=SafetyCar, 5=Red, 6=VSC, 7=VSCEnding
        if isinstance(data, dict):
            status = str(data.get("Status", ""))
        else:
            status = str(data)
        if status:
            race_state.track_status = status
            broadcaster.push()

    def _positions(self, data: str | dict) -> None:
        try:
            raw = _decompress(data) if isinstance(data, str) else data

            # ── normalise to flat {car_num_str: coords_dict} ──────────────
            # Known formats:
            #  A  {"Position": [{"Timestamp":…, "Entries": {"1":{X,Y,Z}, …}}, …]}
            #  B  [{"Timestamp":…, "Entries": {"1":{X,Y,Z}, …}}, …]
            #  C  {"Entries": {"1":{X,Y,Z}, …}}
            flat: dict = {}
            if isinstance(raw, dict):
                frames = raw.get("Position") or []
                if frames:
                    for frame in frames:
                        if isinstance(frame, dict):
                            flat.update(frame.get("Entries") or {})
                elif "Entries" in raw:
                    flat = raw["Entries"]
            elif isinstance(raw, list):
                for frame in raw:
                    if isinstance(frame, dict):
                        flat.update(frame.get("Entries") or {})

            if not flat:
                return

            car_positions = {}
            for num_str, coords in flat.items():
                if not isinstance(coords, dict):
                    continue
                try:
                    num = int(num_str)
                except (ValueError, TypeError):
                    continue
                x = coords.get("X") or coords.get("x")
                y = coords.get("Y") or coords.get("y")
                if x is None or y is None:
                    continue
                driver = race_state.drivers.get(num, {})
                car_positions[num] = {
                    "x":          float(x),
                    "y":          float(y),
                    "code":       driver.get("code", f"#{num}"),
                    "team_color": driver.get("team_color", "#888"),
                }

            if car_positions:
                race_state.car_positions = {**race_state.car_positions, **car_positions}
                logger.info("Position.z: %d cars this msg, %d total tracked",
                            len(car_positions), len(race_state.car_positions))
                broadcaster.push()
        except Exception:
            logger.warning("Position.z decode failed", exc_info=True)

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
            retired = bool(td.get("Retired") or td.get("Stopped"))
            intervals.append({
                "driver_number": num,
                "gap_to_leader": gap,
                "interval":      int_val,
                "retired":       retired,
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

            def _sv(k, _raw=raw_s):
                # Sectors arrives as a list OR a dict with string keys
                if isinstance(_raw, list):
                    s = _raw[k] if k < len(_raw) else {}
                else:
                    s = _raw.get(str(k), {})
                if not isinstance(s, dict):
                    return None, None
                return _parse_time(s.get("Value", ""))

            s1 = _sv(0)
            s2 = _sv(1)
            s3 = _sv(2)

            # Update rolling personal-best minimums for this driver
            pb = self._best_sectors.setdefault(num, {})
            if s1 and s1 > 0:
                pb["s1"] = min(pb.get("s1", float("inf")), s1)
            if s2 and s2 > 0:
                pb["s2"] = min(pb.get("s2", float("inf")), s2)
            if s3 and s3 > 0:
                pb["s3"] = min(pb.get("s3", float("inf")), s3)

            last_raw = td.get("LastLapTime", {})
            best_raw = td.get("BestLapTime", {})
            last_v = last_raw.get("Value", "") if isinstance(last_raw, dict) else ""
            best_v = best_raw.get("Value", "") if isinstance(best_raw, dict) else ""
            best_lap = _parse_time(best_v)
            if best_lap and best_lap > 0:
                pb["lap"] = min(pb.get("lap", float("inf")), best_lap)

            sectors[num] = {
                "sector_1":      s1,
                "sector_2":      s2,
                "sector_3":      s3,
                "best_sector_1": pb.get("s1"),
                "best_sector_2": pb.get("s2"),
                "best_sector_3": pb.get("s3"),
                "lap_time":      _parse_time(last_v),
                "best_lap_time": pb.get("lap"),
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
            # FastF1 sends Stints as a list in the initial R snapshot and as a
            # dict keyed by index string in incremental updates.
            if isinstance(raw_stints, list):
                items = list(enumerate(raw_stints))
            elif isinstance(raw_stints, dict):
                items = list(raw_stints.items())
            else:
                continue
            for idx_key, stint in items:
                if not isinstance(stint, dict):
                    continue
                try:
                    idx = int(idx_key)
                except (ValueError, TypeError):
                    continue
                total = stint.get("TotalLaps", 0)
                start = stint.get("StartLaps", 0)
                stints.append({
                    "driver_number":     num,
                    "stint_number":      idx + 1,
                    "compound":          stint.get("Compound", "UNKNOWN"),
                    "lap_start":         start,
                    "lap_end":           (start + total) if total else None,
                    "tyre_age_at_start": 0,
                    "new_tyre":          stint.get("New", "true") == "true",
                })
        race_state.stints = stints


# ── Public entry point ────────────────────────────────────────────────────────

_service = LiveTimingService()


async def start_live_timing() -> None:
    """
    Spawn the FastF1 SignalR client in a daemon thread.
    Non-blocking: returns immediately. Daemon thread dies with the process,
    so Ctrl+C works even when FastF1 is blocking on auth or a network call.
    """
    _service.reset()
    client = _F1LiveClient(_service)

    def _run():
        try:
            client.start()
            logger.info("FastF1 live timing client exited cleanly.")
        except Exception as exc:
            logger.error("FastF1 live timing client exited with error: %s", exc)
        finally:
            race_state.is_live = False

    t = threading.Thread(target=_run, daemon=True, name="f1-live-timing")
    t.start()
    logger.info("FastF1 live timing thread started.")

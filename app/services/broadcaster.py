import asyncio
import logging
import threading

from app.core.state import race_state

logger = logging.getLogger(__name__)


def _build_snapshot() -> dict:
    return {
        "meeting":           race_state.meeting_name,
        "session_key":       race_state.session_key,
        "session_type":      race_state.session_type,
        "lap_number":        race_state.lap_number,
        "total_laps":        race_state.total_laps,
        "session_remaining": race_state.session_remaining,
        "is_live":           race_state.is_live,
        "last_updated":      race_state.last_updated.isoformat() if race_state.last_updated else None,
        "drivers":           race_state.drivers,
        "positions":         race_state.normalized_positions,
        "intervals":         race_state.intervals,
        "tyres":             race_state.stints,
        "sectors":           race_state.sectors_by_driver,
        "weather":           race_state.weather,
        "race_control":      race_state.race_control,
        "pit_stops":         race_state.pit_stops,
    }


class Broadcaster:
    """
    Thread-safe pub/sub hub.

    FastF1 worker thread calls push() → snapshot is built and enqueued on
    every connected client's asyncio.Queue via call_soon_threadsafe.
    WebSocket handlers drain their queue and send the latest payload.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: set[asyncio.Queue] = set()
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def add(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._queues.add(q)

    def remove(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._queues.discard(q)

    def push(self) -> None:
        """Build snapshot and broadcast to all WS clients. Safe to call from any thread."""
        if not self._loop:
            return
        snapshot = _build_snapshot()
        with self._lock:
            queues = list(self._queues)
        for q in queues:
            self._loop.call_soon_threadsafe(q.put_nowait, snapshot)

    def snapshot(self) -> dict:
        """Return the current snapshot dict (for the initial WS send on connect)."""
        return _build_snapshot()


broadcaster = Broadcaster()

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.state import race_state
from app.services.openf1_client import openf1_client
from app.services.map_builder import build_car_positions
from app.services.broadcaster import broadcaster

logger = logging.getLogger(__name__)

POLL_INTERVAL   = 2   # seconds between location polls
WINDOW_SECONDS  = 5   # fetch positions from the last N seconds
_401_LOG_EVERY  = 60  # suppress repeated 401 warnings


async def poll_car_positions() -> None:
    """
    Poll OpenF1 /location every 2 s and push car positions to the track map.
    Only runs while the session is live and the session key is known.
    Never exits — handles errors silently and retries.
    """
    last_401_log = 0.0

    while True:
        if not race_state.is_live or not race_state.session_key:
            await asyncio.sleep(1)
            continue

        try:
            date_gte = (
                datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            locations = await openf1_client.get_locations(
                race_state.session_key, date_gte=date_gte
            )

            if locations:
                race_state.car_positions = build_car_positions(
                    locations, race_state.drivers
                )
                broadcaster.push()

        except Exception as exc:
            import time as _time
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 401:
                now = _time.monotonic()
                if now - last_401_log >= _401_LOG_EVERY:
                    logger.warning("Track map: OpenF1 /location returned 401 — retrying")
                    last_401_log = now
            else:
                logger.debug("Track map poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)

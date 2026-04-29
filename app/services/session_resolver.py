import asyncio
import logging
from datetime import datetime, timezone

from app.core.utils import parse_dt
from app.services.openf1_client import openf1_client

logger = logging.getLogger(__name__)


async def resolve_race_session():
    sessions = await openf1_client.get_race_sessions()
    if not sessions:
        return None, False

    now = datetime.now(timezone.utc)

    # 1️⃣ Look for a currently live race (must have actual position data to be
    #    considered truly live — guards against OpenF1 publishing a session entry
    #    before the race has actually started)
    for s in sessions:
        if not s.get("date_start"):
            continue
        start = parse_dt(s["date_start"])
        end = parse_dt(s["date_end"]) if s.get("date_end") else None

        if start <= now and (end is None or now <= end):
            positions = await openf1_client.get_positions(s["session_key"])
            if positions:
                return s, True
            logger.info(
                "Session %s looks live by time but has no position data yet — skipping.",
                s.get("session_key"),
            )

    # 2️⃣ Find the most recent finished race that has actual data.
    #    Canceled races exist in OpenF1 with a past date but return no positions.
    finished = [
        s for s in sessions
        if s.get("date_end") and parse_dt(s["date_end"]) < now
    ]
    finished.sort(key=lambda s: parse_dt(s["date_end"]), reverse=True)

    for s in finished:
        await asyncio.sleep(0.5)
        positions = await openf1_client.get_positions(s["session_key"])
        if positions:
            return s, False
        logger.warning(
            "Session %s (%s) has no position data — skipping (likely canceled).",
            s.get("session_key"),
            s.get("meeting_name", "unknown"),
        )

    return None, False

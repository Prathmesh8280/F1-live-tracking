import asyncio
import logging
from datetime import datetime, timezone

from app.core.utils import parse_dt
from app.services.openf1_client import openf1_client

logger = logging.getLogger(__name__)


async def resolve_race_session():
    now = datetime.now(timezone.utc)

    # Fetch all sessions (no year filter — OpenF1 rejects year param with 401).
    # The full list is ~1000 entries going back to 2018; we sort and search quickly.
    sessions = await openf1_client.get_sessions()
    if not sessions:
        logger.warning("OpenF1 returned no sessions at all.")
        return None, False

    # 1️⃣ Look for a currently live session (any type). Must have position
    #    data to be considered truly live — guards against OpenF1 publishing
    #    a session entry before it has actually started.
    for s in sessions:
        if not s.get("date_start"):
            continue
        start = parse_dt(s["date_start"])
        end   = parse_dt(s["date_end"]) if s.get("date_end") else None

        if start <= now and (end is None or now <= end):
            positions = await openf1_client.get_positions(s["session_key"])
            if positions:
                logger.info(
                    "Live session found: %s %s (key %s).",
                    s.get("meeting_name", ""), s.get("session_name", ""),
                    s.get("session_key"),
                )
                return s, True
            logger.info(
                "Session %s looks live by time but has no position data yet — skipping.",
                s.get("session_key"),
            )

    # 2️⃣ Find the most recent finished session that has actual data.
    #    Cancelled sessions exist in OpenF1 but return no positions.
    finished = [
        s for s in sessions
        if s.get("date_end") and parse_dt(s["date_end"]) < now
    ]
    finished.sort(key=lambda s: parse_dt(s["date_end"]), reverse=True)

    for s in finished:
        await asyncio.sleep(0.3)
        positions = await openf1_client.get_positions(s["session_key"])
        if positions:
            logger.info(
                "Most recent finished session: %s %s (key %s).",
                s.get("meeting_name", ""), s.get("session_name", ""),
                s.get("session_key"),
            )
            return s, False
        logger.warning(
            "Session %s (%s %s) has no position data — skipping (likely cancelled).",
            s.get("session_key"),
            s.get("meeting_name", "unknown"),
            s.get("session_name", ""),
        )

    return None, False

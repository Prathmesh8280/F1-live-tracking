from datetime import datetime, timezone
from app.services.openf1_client import OpenF1Client

client = OpenF1Client()

async def resolve_race_session():
    sessions = await client.get_race_sessions()
    if not sessions:
        return None, False

    now = datetime.now(timezone.utc)

    # 1️⃣ Look for live race
    for s in sessions:
        start = datetime.fromisoformat(s["date_start"])
        end = datetime.fromisoformat(s["date_end"]) if s["date_end"] else None

        if start <= now and (end is None or now <= end):
            return s, True

    # 2️⃣ Pick most recent FINISHED race
    finished = []
    for s in sessions:
        if s["date_end"]:
            end = datetime.fromisoformat(s["date_end"])
            if end < now:
                finished.append(s)

    if not finished:
        return None, False

    finished.sort(key=lambda s: s["date_end"], reverse=True)
    return finished[0], False

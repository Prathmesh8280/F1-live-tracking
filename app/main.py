import asyncio
from datetime import datetime
from fastapi import FastAPI

from app.core.state import race_state
from app.api.race import router as race_router
from app.services.session_resolver import resolve_race_session
from app.services.poller import poll_live_race
from app.services.openf1_client import OpenF1Client
from app.services.sector_builder import build_latest_sectors
from app.services.driver_builder import build_driver_map
from app.services.position_builder import normalize_positions
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="F1 Live Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(race_router)

client = OpenF1Client()


@app.on_event("startup")
async def startup():
    # 1️⃣ Resolve which race session to use
    session, is_live = await resolve_race_session()
    if not session:
        print("No valid race session found.")
        return

    race_state.session_key = session["session_key"]
    race_state.meeting_key = session["meeting_key"]
    race_state.is_live = is_live

    # 2️⃣ Fetch meeting details
    meeting = await client.get_meeting(session["meeting_key"])
    if meeting:
        race_state.meeting_name = meeting.get("meeting_name")

    # 3️⃣ Fetch and normalize drivers
    drivers = await client.get_drivers(session["session_key"])
    race_state.drivers = build_driver_map(drivers)

    # 4️⃣ Load initial race data
    raw_positions = await client.get_positions(session["session_key"])
    race_state.normalized_positions = normalize_positions(
        raw_positions,
        race_state.drivers
    )
    race_state.intervals = await client.get_intervals(session["session_key"])
    race_state.stints = await client.get_stints(session["session_key"])

    # 5️⃣ Load laps and compute lap number + sector times
    laps = await client.get_laps(session["session_key"])
    if laps:
        race_state.lap_number = max(l["lap_number"] for l in laps)
        race_state.sectors_by_driver = build_latest_sectors(laps)

    race_state.last_updated = datetime.utcnow()

    # 6️⃣ Start poller ONLY if race is live
    if is_live:
        asyncio.create_task(poll_live_race())
        print(f"🟢 Live race detected: {race_state.meeting_name}")
    else:
        print(f"🔵 No live race. Showing last finished race: {race_state.meeting_name}")

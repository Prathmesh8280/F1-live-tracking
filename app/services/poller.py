import asyncio
from datetime import datetime

from app.core.state import race_state
from app.services.openf1_client import OpenF1Client
from app.services.sector_builder import build_latest_sectors
from app.services.position_builder import normalize_positions


client = OpenF1Client()

async def poll_live_race():
    while race_state.is_live:
        try:
            session_key = race_state.session_key

            raw_positions = await client.get_positions(race_state.session_key)
            race_state.normalized_positions = normalize_positions(
                raw_positions,
                race_state.drivers
            )

            race_state.intervals = await client.get_intervals(session_key)
            race_state.stints = await client.get_stints(session_key)

            laps = await client.get_laps(session_key)
            if laps:
                race_state.lap_number = max(l["lap_number"] for l in laps)
                race_state.sectors_by_driver = build_latest_sectors(laps)


            race_state.last_updated = datetime.utcnow()

        except Exception as e:
            print("Polling error:", e)

        await asyncio.sleep(2)

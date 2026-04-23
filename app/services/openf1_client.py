import httpx

BASE_URL = "https://api.openf1.org/v1"

class OpenF1Client:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10)

    async def get_race_sessions(self):
        resp = await self.client.get(
            f"{BASE_URL}/sessions",
            params={"session_name": "Race"}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_positions(self, session_key: int):
        resp = await self.client.get(
            f"{BASE_URL}/position",
            params={"session_key": session_key}
        )
        return resp.json()

    async def get_intervals(self, session_key: int):
        resp = await self.client.get(
            f"{BASE_URL}/intervals",
            params={"session_key": session_key}
        )
        return resp.json()

    async def get_stints(self, session_key: int):
        resp = await self.client.get(
            f"{BASE_URL}/stints",
            params={"session_key": session_key}
        )
        return resp.json()

    async def get_laps(self, session_key: int):
        resp = await self.client.get(
            f"{BASE_URL}/laps",
            params={"session_key": session_key}
        )
        return resp.json()
    
    async def get_meeting(self, meeting_key: int):
        resp = await self.client.get(
            f"{BASE_URL}/meetings",
            params={"meeting_key": meeting_key}
        )
        resp.raise_for_status()
        meetings = resp.json()
        return meetings[0] if meetings else None
    
    async def get_drivers(self, session_key: int):
        resp = await self.client.get(
            f"{BASE_URL}/drivers",
            params={"session_key": session_key}
        )
        resp.raise_for_status()
        return resp.json()



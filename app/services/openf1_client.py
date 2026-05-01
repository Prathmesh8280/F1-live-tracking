import asyncio
import logging

import httpx

BASE_URL = "https://api.openf1.org/v1"
logger = logging.getLogger(__name__)


def _list_or_empty(resp: httpx.Response) -> list:
    """Return parsed JSON list, or [] if 404 (data not available yet)."""
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


class OpenF1Client:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10)

    async def close(self):
        await self.client.aclose()

    async def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        """GET with automatic retry on 429 (exponential backoff: 2s, 4s, 8s)."""
        for attempt in range(4):
            resp = await self.client.get(url, params=params)
            if resp.status_code != 429:
                return resp
            wait = 2 ** (attempt + 1)
            logger.warning("Rate limited by OpenF1 — retrying in %ds (attempt %d)", wait, attempt + 1)
            await asyncio.sleep(wait)
        return resp  # return last response after exhausting retries

    async def get_sessions(self) -> list:
        resp = await self._get(f"{BASE_URL}/sessions")
        if resp.status_code in (401, 404):
            return []
        resp.raise_for_status()
        return resp.json()

    async def get_positions(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/position", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_intervals(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/intervals", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_stints(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/stints", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_laps(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/laps", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_meeting(self, meeting_key: int):
        resp = await self._get(f"{BASE_URL}/meetings", params={"meeting_key": meeting_key})
        resp.raise_for_status()
        meetings = resp.json()
        return meetings[0] if meetings else None

    async def get_drivers(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/drivers", params={"session_key": session_key})
        resp.raise_for_status()
        return resp.json()

    async def get_pit_stops(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/pit", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_weather(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/weather", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_race_control(self, session_key: int):
        resp = await self._get(f"{BASE_URL}/race_control", params={"session_key": session_key})
        return _list_or_empty(resp)

    async def get_locations(
        self,
        session_key: int,
        driver_number: int | None = None,
        date_gte: str | None = None,
        date_lte: str | None = None,
    ) -> list:
        # Build URL manually — OpenF1 uses "date>=" as the literal param name
        # which httpx would percent-encode incorrectly via the params dict.
        url = f"{BASE_URL}/location?session_key={session_key}"
        if driver_number is not None:
            url += f"&driver_number={driver_number}"
        if date_gte:
            url += f"&date>={date_gte}"
        if date_lte:
            url += f"&date<={date_lte}"
        resp = await self._get(url)
        return _list_or_empty(resp)


# Shared singleton — import this everywhere instead of creating new instances
openf1_client = OpenF1Client()

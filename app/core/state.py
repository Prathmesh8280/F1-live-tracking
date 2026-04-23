from typing import List, Dict, Optional
from datetime import datetime

class RaceState:
    session_key: Optional[int] = None
    meeting_key: Optional[int] = None
    meeting_name: Optional[str] = None
    lap_number: Optional[int] = None

    positions: List[Dict] = []
    intervals: List[Dict] = []
    stints: List[Dict] = []
    drivers: dict[int, dict] = {}
    normalized_positions: list[dict] = []

    sectors_by_driver: Dict[int, Dict] = {}

    is_live: bool = False
    last_updated: Optional[datetime] = None


race_state = RaceState()

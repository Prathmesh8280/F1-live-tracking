from datetime import datetime
from typing import Optional


class RaceState:
    def __init__(self):
        self.session_key: Optional[int] = None
        self.meeting_key: Optional[int] = None
        self.meeting_name: Optional[str] = None
        self.lap_number: Optional[int] = None

        self.normalized_positions: list[dict] = []
        self.intervals: list[dict] = []
        self.stints: list[dict] = []
        self.drivers: dict[int, dict] = {}
        self.sectors_by_driver: dict[int, dict] = {}

        self.track_outline: list[dict] = []
        self.sector_fractions: list[float] = []
        self.car_positions: dict[int, dict] = {}

        self.weather: dict = {}
        self.race_control: list[dict] = []

        self.is_live: bool = False
        self.last_updated: Optional[datetime] = None


race_state = RaceState()

from datetime import datetime, timezone


def parse_dt(value: str) -> datetime:
    """Parse an ISO 8601 string and ensure it is timezone-aware (UTC)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

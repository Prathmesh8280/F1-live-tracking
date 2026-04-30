from datetime import datetime, timezone


def parse_dt(value: str) -> datetime:
    """Parse an ISO 8601 string and ensure it is timezone-aware (UTC).
    Replaces trailing Z before parsing for Python 3.10 compatibility."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

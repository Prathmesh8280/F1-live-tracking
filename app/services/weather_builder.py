def latest_weather(records: list[dict]) -> dict:
    """Return the most recent weather reading from a list of weather records."""
    if not records:
        return {}
    latest = max(records, key=lambda r: r.get("date", ""))
    return {
        "air_temp":        latest.get("air_temperature"),
        "track_temp":      latest.get("track_temperature"),
        "humidity":        latest.get("humidity"),
        "pressure":        latest.get("pressure"),
        "wind_speed":      latest.get("wind_speed"),
        "wind_direction":  latest.get("wind_direction"),
        "rainfall":        latest.get("rainfall", False),
    }

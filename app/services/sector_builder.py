def build_latest_sectors(laps: list[dict]) -> dict:
    """
    Returns latest completed lap sector times per driver.
    """
    latest = {}

    for lap in laps:
        if lap.get("is_deleted"):
            continue

        driver = lap["driver_number"]
        lap_number = lap["lap_number"]

        if driver not in latest or lap_number > latest[driver]["lap_number"]:
            latest[driver] = {
                "lap_number": lap_number,
                "lap_time": lap.get("lap_duration"),
                "sector_1": lap.get("duration_sector_1"),
                "sector_2": lap.get("duration_sector_2"),
                "sector_3": lap.get("duration_sector_3"),
            }

    return latest

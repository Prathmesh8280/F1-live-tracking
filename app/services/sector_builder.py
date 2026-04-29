def build_latest_sectors(laps: list[dict]) -> dict:
    """
    Returns latest completed lap sector times + personal best lap time per driver.
    """
    latest = {}
    best: dict[int, float] = {}

    for lap in laps:
        if lap.get("is_deleted"):
            continue

        driver = lap["driver_number"]
        lap_number = lap["lap_number"]
        lap_duration = lap.get("lap_duration")

        if driver not in latest or lap_number > latest[driver]["lap_number"]:
            latest[driver] = {
                "lap_number": lap_number,
                "lap_time": lap_duration,
                "sector_1": lap.get("duration_sector_1"),
                "sector_2": lap.get("duration_sector_2"),
                "sector_3": lap.get("duration_sector_3"),
            }

        if lap_duration is not None:
            if driver not in best or lap_duration < best[driver]:
                best[driver] = lap_duration

    for driver, data in latest.items():
        data["best_lap_time"] = best.get(driver)

    return latest

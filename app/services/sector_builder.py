def build_latest_sectors(laps: list[dict]) -> dict:
    """
    Returns latest completed lap sector times, personal best lap time, and
    personal best sector times per driver.
    """
    latest = {}
    best_lap:  dict[int, float] = {}
    best_s1:   dict[int, float] = {}
    best_s2:   dict[int, float] = {}
    best_s3:   dict[int, float] = {}

    for lap in laps:
        if lap.get("is_deleted"):
            continue

        driver       = lap["driver_number"]
        lap_number   = lap["lap_number"]
        lap_duration = lap.get("lap_duration")
        s1 = lap.get("duration_sector_1")
        s2 = lap.get("duration_sector_2")
        s3 = lap.get("duration_sector_3")

        if driver not in latest or lap_number > latest[driver]["lap_number"]:
            latest[driver] = {
                "lap_number": lap_number,
                "lap_time":   lap_duration,
                "sector_1":   s1,
                "sector_2":   s2,
                "sector_3":   s3,
            }

        if lap_duration is not None and (driver not in best_lap or lap_duration < best_lap[driver]):
            best_lap[driver] = lap_duration
        if s1 is not None and (driver not in best_s1 or s1 < best_s1[driver]):
            best_s1[driver] = s1
        if s2 is not None and (driver not in best_s2 or s2 < best_s2[driver]):
            best_s2[driver] = s2
        if s3 is not None and (driver not in best_s3 or s3 < best_s3[driver]):
            best_s3[driver] = s3

    for driver, data in latest.items():
        data["best_lap_time"] = best_lap.get(driver)
        data["best_sector_1"] = best_s1.get(driver)
        data["best_sector_2"] = best_s2.get(driver)
        data["best_sector_3"] = best_s3.get(driver)

    return latest

def normalize_positions(
    raw_positions: list[dict],
    drivers: dict[int, dict],
) -> list[dict]:
    """
    Combines raw OpenF1 positions with driver metadata.
    OpenF1 returns full position history — we keep only the latest entry per
    driver (highest date value) before building the sorted leaderboard.
    """
    # Deduplicate: keep the most recent position entry per driver
    latest_by_driver: dict[int, dict] = {}
    for p in raw_positions:
        number = p.get("driver_number")
        if number is None:
            continue
        existing = latest_by_driver.get(number)
        if existing is None or (p.get("date", "") > existing.get("date", "")):
            latest_by_driver[number] = p

    normalized = []
    for driver_number, p in latest_by_driver.items():
        driver = drivers.get(driver_number)
        if not driver:
            continue

        position = p.get("position")
        normalized.append({
            "position": position,
            "driver": {
                "number": driver["number"],
                "code": driver["code"],
                "team_color": driver["team_color"],
            },
        })

    # Sort with None positions pushed to the end
    return sorted(normalized, key=lambda x: (x["position"] is None, x["position"] or 0))

def normalize_positions(
    raw_positions: list[dict],
    drivers: dict[int, dict]
) -> list[dict]:
    """
    Combines raw OpenF1 positions with normalized driver metadata.
    Returns sorted timing-tower-ready position list.
    """
    normalized = []

    for p in raw_positions:
        driver_number = p.get("driver_number")
        driver = drivers.get(driver_number)

        if not driver:
            continue

        normalized.append({
            "position": p.get("position"),
            "driver": {
                "number": driver["number"],
                "code": driver["code"],
                "name": f'{driver["first_name"]} {driver["last_name"]}',
                "team": driver["team"],
                "team_color": driver["team_color"]
            }
        })

    return sorted(normalized, key=lambda x: x["position"])

def build_driver_map(drivers: list[dict]) -> dict[int, dict]:
    driver_map = {}

    for d in drivers:
        number = d.get("driver_number")
        if number is None:
            continue

        # OpenF1 uses "name_acronym" for the 3-letter code (HAM, VER, etc.)
        driver_map[number] = {
            "number": number,
            "code": d.get("name_acronym"),
            "team_color": f"#{d.get('team_colour')}" if d.get("team_colour") else None,
        }

    return driver_map

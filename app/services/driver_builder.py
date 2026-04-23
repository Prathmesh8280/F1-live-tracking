def build_driver_map(drivers: list[dict]) -> dict[int, dict]:
    """
    Normalizes driver metadata into a dictionary keyed by driver number.
    """
    driver_map = {}

    for d in drivers:
        number = d["driver_number"]
        driver_map[number] = {
            "number": number,
            "code": d.get("driver_code"),
            "first_name": d.get("first_name"),
            "last_name": d.get("last_name"),
            "team": d.get("team_name"),
            "team_color": f"#{d.get('team_colour')}" if d.get("team_colour") else None
        }

    return driver_map

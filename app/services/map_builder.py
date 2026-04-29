def extract_outline_points(locations: list[dict]) -> list[dict]:
    """Reduce raw location records to a list of {x, y} points for the track outline."""
    return [
        {"x": loc["x"], "y": loc["y"]}
        for loc in locations
        if loc.get("x") is not None and loc.get("y") is not None
    ]


def build_car_positions(locations: list[dict], drivers: dict[int, dict]) -> dict[int, dict]:
    """
    Return the most recent x/y position per driver, enriched with driver metadata.
    Locations list must already be filtered to the relevant time window.
    """
    latest: dict[int, dict] = {}
    for loc in locations:
        n = loc.get("driver_number")
        if n is None or loc.get("x") is None or loc.get("y") is None:
            continue
        if n not in latest or loc.get("date", "") > latest[n].get("date", ""):
            latest[n] = {"x": loc["x"], "y": loc["y"], "date": loc.get("date", "")}

    result: dict[int, dict] = {}
    for n, pos in latest.items():
        driver = drivers.get(n, {})
        result[n] = {
            "x": pos["x"],
            "y": pos["y"],
            "code": driver.get("code"),
            "team_color": driver.get("team_color"),
        }
    return result

from fastapi import APIRouter
from app.core.state import race_state

router = APIRouter(prefix="/race", tags=["Race"])


@router.get("/status")
def status():
    return {
        "meeting": race_state.meeting_name,
        "lap": race_state.lap_number,
        "is_live": race_state.is_live,
        "updated_at": race_state.last_updated,
    }


@router.get("/positions")
def positions():
    return race_state.normalized_positions


@router.get("/intervals")
def intervals():
    return race_state.intervals


@router.get("/tyres")
def tyres():
    return race_state.stints


@router.get("/sectors")
def sectors():
    return race_state.sectors_by_driver


@router.get("/timing_tower")
def timing_tower():
    return {
        "meeting": race_state.meeting_name,
        "session_key": race_state.session_key,
        "lap_number": race_state.lap_number,
        "is_live": race_state.is_live,
        "last_updated": race_state.last_updated,
        "drivers": race_state.drivers,
        "positions": race_state.normalized_positions,
        "intervals": race_state.intervals,
        "tyres": race_state.stints,
        "sectors": race_state.sectors_by_driver,
        "weather": race_state.weather,
        "race_control": race_state.race_control,
        "pit_stops": race_state.pit_stops,
    }


@router.get("/map")
def map_data():
    return {
        "is_live": race_state.is_live,
        "track_outline": race_state.track_outline,
        "sector_fractions": race_state.sector_fractions,
        "car_positions": race_state.car_positions,
    }

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.state import race_state
from app.services.broadcaster import broadcaster

router = APIRouter(prefix="/race", tags=["Race"])
logger = logging.getLogger(__name__)


@router.get("/status")
def status():
    return {
        "meeting":    race_state.meeting_name,
        "lap":        race_state.lap_number,
        "is_live":    race_state.is_live,
        "updated_at": race_state.last_updated,
    }


@router.get("/timing_tower")
def timing_tower():
    return broadcaster.snapshot()


@router.get("/map")
def map_data():
    return {
        "is_live":         race_state.is_live,
        "track_outline":   race_state.track_outline,
        "sector_fractions": race_state.sector_fractions,
        "car_positions":   race_state.car_positions,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue()
    broadcaster.add(q)
    try:
        # Send the current full state the moment the client connects
        await websocket.send_json(broadcaster.snapshot())
        while True:
            data = await q.get()
            # Drain: if rapid updates queued up, send only the newest
            try:
                while True:
                    data = q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        broadcaster.remove(q)

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.race import router as race_router
from app.services.live_timing import start_live_timing
from app.services.broadcaster import broadcaster
from app.services.openf1_client import openf1_client
from app.services.poller import poll_car_positions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress FastF1's internal chatty loggers — only show WARNING and above
for _noisy in ("fastf1", "fastf1.fastf1", "fastf1.api", "fastf1.fastf1.req",
               "fastf1.fastf1.core", "fastf1.logger", "SignalR",
               "signalrcore", "websockets", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

_LIVE_WAIT_SECONDS = 15  # how long to wait for FastF1 before loading historical


async def _historical_fallback() -> None:
    """Wait for a live session; if none arrives, load the last completed session."""
    await asyncio.sleep(_LIVE_WAIT_SECONDS)
    from app.core.state import race_state
    if race_state.meeting_name:
        return  # FastF1 already delivered session data
    logger.info("No live session after %ds — loading last completed session from FastF1", _LIVE_WAIT_SECONDS)
    from app.services.historical_loader import load_last_session
    success = await load_last_session()
    if not success:
        logger.warning("Historical fallback also failed — UI will show empty state")


@asynccontextmanager
async def lifespan(app: FastAPI):
    broadcaster.set_loop(asyncio.get_running_loop())
    await start_live_timing()
    asyncio.create_task(poll_car_positions())
    asyncio.create_task(_historical_fallback())
    logger.info("F1 live timing started.")
    yield
    from app.core.state import race_state
    race_state.is_live = False
    await openf1_client.close()
    logger.info("Shutdown complete.")


app = FastAPI(title="F1 Live Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(race_router)

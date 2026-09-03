import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from api.config import CORS_ORIGINS
from api.exceptions import (
    EngineNotFoundError,
    MissionNotFoundError,
    InvalidTimeRangeError,
    BackendUnavailableError,
    engine_not_found_handler,
    mission_not_found_handler,
    invalid_time_range_handler,
    backend_unavailable_handler,
)
from api.routers import engines, missions, dashboard
from api.websocket import ws_manager, websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    broadcast_task = asyncio.create_task(ws_manager.run())

    yield

    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Digital Twin API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(EngineNotFoundError, engine_not_found_handler)
app.add_exception_handler(MissionNotFoundError, mission_not_found_handler)
app.add_exception_handler(InvalidTimeRangeError, invalid_time_range_handler)
app.add_exception_handler(BackendUnavailableError, backend_unavailable_handler)

app.include_router(engines.router, prefix="/api")
app.include_router(missions.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.websocket("/ws/engines/{engine_id}")
async def ws_route(websocket: WebSocket, engine_id: str, mission_id: str):
    await websocket_endpoint(websocket, engine_id, mission_id)
from fastapi import Request
from fastapi.responses import JSONResponse


class EngineNotFoundError(Exception):
    def __init__(self, engine_id: str):
        self.engine_id = engine_id


class MissionNotFoundError(Exception):
    def __init__(self, mission_id: str):
        self.mission_id = mission_id


class InvalidTimeRangeError(Exception):
    def __init__(self, message: str):
        self.message = message


class BackendUnavailableError(Exception):
    def __init__(self, message: str = "A required backend dependency is unavailable"):
        self.message = message


async def engine_not_found_handler(request: Request, exc: EngineNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Engine '{exc.engine_id}' not found"},
    )


async def mission_not_found_handler(request: Request, exc: MissionNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Mission '{exc.mission_id}' not found"},
    )


async def invalid_time_range_handler(request: Request, exc: InvalidTimeRangeError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message},
    )


async def backend_unavailable_handler(request: Request, exc: BackendUnavailableError):
    return JSONResponse(
        status_code=503,
        content={"detail": exc.message},
    )
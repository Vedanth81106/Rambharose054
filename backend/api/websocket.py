import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from telemetry.database import SessionLocal
from telemetry.repository import TelemetryRepository
from twin.repository import HealthSnapshotRepository
from twin.factory import create_digital_twin_service
from twin.ml_predictor import ModelPredictor
from twin.schemas import MLPrediction
import traceback

POLL_INTERVAL_SECONDS = 2

_telemetry_repo = TelemetryRepository()
_health_repo = HealthSnapshotRepository()
_twin_service = create_digital_twin_service(ModelPredictor())


class ConnectionManager:
    def __init__(self):
        self.connections: dict[tuple[str, str], set[WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        engine_id: str,
        mission_id: str,
    ):
        await websocket.accept()

        key = (engine_id, mission_id)
        self.connections.setdefault(key, set()).add(websocket)
        print(f"[WS] Connected: {engine_id}/{mission_id}")

    def disconnect(
        self,
        websocket: WebSocket,
        engine_id: str,
        mission_id: str,
    ):
        key = (engine_id, mission_id)

        if key in self.connections:
            self.connections[key].discard(websocket)

            if not self.connections[key]:
                del self.connections[key]

    async def run(self):
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            try:
                await self._poll_and_broadcast()
            except Exception:
                print("[WS] Broadcast error:")
                traceback.print_exc()

    async def _poll_and_broadcast(self):
        for key in list(self.connections.keys()):
            engine_id, mission_id = key
            sockets = self.connections.get(key)

            if not sockets:
                continue

            payload = self._build_payload(engine_id, mission_id)
            print(f"[WS] Broadcasting: {engine_id}/{mission_id}")

            if payload is None:
                continue

            dead = set()

            for websocket in sockets:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    dead.add(websocket)

            for websocket in dead:
                sockets.discard(websocket)

    def _build_payload(
        self,
        engine_id: str,
        mission_id: str,
    ) -> dict | None:

        session = SessionLocal()

        try:
            latest_row = _telemetry_repo.get_latest(
                session,
                engine_id,
                mission_id,
            )

            if latest_row is None:
                return None

            telemetry = {
                "timestamp": latest_row.time.isoformat(),
                "engine_id": latest_row.engine_id,
                "mission_id": latest_row.mission_id,
                "rpm": latest_row.rpm,
                "torque": latest_row.torque,
                "cht": latest_row.cht,
                "egt": latest_row.egt,
                "oil_pressure": latest_row.oil_pressure,
                "oil_temperature": latest_row.oil_temperature,
                "fuel_flow": latest_row.fuel_flow,
                "vibration": latest_row.vibration,
            }

            snapshots = _health_repo.get_by_engine(
                session,
                engine_id,
            )

            snapshots = [
                s
                for s in snapshots
                if s.mission_id == mission_id
            ]

            health = None

            if snapshots:
                snapshot = snapshots[-1]

                health = {
                    "overall": snapshot.overall,
                    "thermal": snapshot.thermal,
                    "combustion": snapshot.combustion,
                    "lubrication": snapshot.lubrication,
                    "mechanical": snapshot.mechanical,
                }

            window = _telemetry_repo.get_latest_window(
                session,
                engine_id,
                mission_id,
            )

            if len(window) < 60:
                ml_prediction = MLPrediction(
                    anomaly_score=0.0,
                    fault=None,
                    confidence=0.0,
                    rul_hours=None,
                )

            else:
                telemetry_window = [
                    {
                        "rpm": t.rpm,
                        "cht": t.cht,
                        "egt": t.egt,
                        "oil_pressure": t.oil_pressure,
                        "oil_temperature": t.oil_temperature,
                        "fuel_flow": t.fuel_flow,
                        "vibration": t.vibration,
                        "torque": t.torque,
                        
                        "throttle": t.throttle,
                        "engine_load": t.engine_load,
                        "altitude": t.altitude,
                        "ambient_temperature": t.ambient_temperature,
                    }
                    for t in window
                ]
                ml_prediction = (
                    _twin_service.predictor.predict(
                        telemetry_window
                    )
                )

            prediction = {
                "anomaly_score": ml_prediction.anomaly_score,
                "fault": ml_prediction.fault,
                "confidence": ml_prediction.confidence,
                "rul_hours": ml_prediction.rul_hours,
            }

            operating_state = None

            if health is not None:
                operating_state = (
                    _twin_service._determine_operating_state(
                        health["overall"],
                        ml_prediction,
                    )
                )

            return {
                "type": "engine_update",
                "engine_id": engine_id,
                "mission_id": mission_id,
                "telemetry": telemetry,
                "health": health,
                "prediction": prediction,
                "operating_state": operating_state,
            }

        finally:
            session.close()


ws_manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    engine_id: str,
    mission_id: str,
):
    await ws_manager.connect(
        websocket,
        engine_id,
        mission_id,
    )

    try:
        while True:
            await asyncio.sleep(60)

    except WebSocketDisconnect:
        ws_manager.disconnect(
            websocket,
            engine_id,
            mission_id,
        )

    except Exception:
        ws_manager.disconnect(
            websocket,
            engine_id,
            mission_id,
        )
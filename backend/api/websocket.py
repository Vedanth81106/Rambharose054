import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from telemetry.database import SessionLocal
from telemetry.repository import TelemetryRepository
from twin.repository import HealthSnapshotRepository
from twin.factory import create_digital_twin_service
from twin.ml_predictor import ModelPredictor
from twin.schemas import MLPrediction

POLL_INTERVAL_SECONDS = 2

_telemetry_repo = TelemetryRepository()
_health_repo = HealthSnapshotRepository()
_twin_service = create_digital_twin_service(ModelPredictor())


class ConnectionManager:
    def __init__(self):
        # (engine_id, mission_id) -> set of active websockets
        self.connections: dict[tuple[str, str], set[WebSocket]] = {}
        # (engine_id, mission_id) -> last payload sent, for diffing
        self.last_sent: dict[tuple[str, str], dict] = {}

    async def connect(self, websocket: WebSocket, engine_id: str, mission_id: str):
        await websocket.accept()
        key = (engine_id, mission_id)
        self.connections.setdefault(key, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, engine_id: str, mission_id: str):
        key = (engine_id, mission_id)
        if key in self.connections:
            self.connections[key].discard(websocket)
            if not self.connections[key]:
                del self.connections[key]
                self.last_sent.pop(key, None)

    async def run(self):
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            await self._poll_and_broadcast()

    async def _poll_and_broadcast(self):
        for key in list(self.connections.keys()):
            engine_id, mission_id = key
            sockets = self.connections.get(key)
            if not sockets:
                continue

            payload = self._build_payload(engine_id, mission_id)
            if payload is None:
                continue

            if self.last_sent.get(key) == payload:
                continue

            self.last_sent[key] = payload

            dead = set()
            for ws in sockets:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.add(ws)

            for ws in dead:
                sockets.discard(ws)

    def _build_payload(self, engine_id: str, mission_id: str) -> dict | None:
        session = SessionLocal()
        try:
            latest_row = _telemetry_repo.get_latest(session, engine_id, mission_id)
            if latest_row is None:
                return None

            telemetry = {
                "timestamp": latest_row.time.isoformat(),
                "rpm": latest_row.rpm,
                "cht": latest_row.cht,
                "egt": latest_row.egt,
                "oil_pressure": latest_row.oil_pressure,
                "oil_temperature": latest_row.oil_temperature,
                "fuel_flow": latest_row.fuel_flow,
                "vibration": latest_row.vibration,
                "battery_voltage": latest_row.battery_voltage,
                "alternator_current": latest_row.alternator_current,
                "injection_timing": latest_row.injection_timing,
            }

            snapshots = _health_repo.get_by_engine(session, engine_id)
            snapshots = [s for s in snapshots if s.mission_id == mission_id]

            health = None
            operating_state = None
            if snapshots:
                s = snapshots[-1]
                health = {
                    "overall": s.overall,
                    "thermal": s.thermal,
                    "combustion": s.combustion,
                    "lubrication": s.lubrication,
                    "mechanical": s.mechanical,
                    "electrical": s.electrical,
                }

            window = _telemetry_repo.get_latest_window(session, engine_id, mission_id)
            if len(window) < 60:
                ml_prediction = MLPrediction(
                    anomaly_score=0.0, fault=None, confidence=0.0, rul_hours=None
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
                        "battery_voltage": t.battery_voltage,
                        "alternator_current": t.alternator_current,
                        "injection_timing": t.injection_timing,
                    }
                    for t in window
                ]
                ml_prediction = _twin_service.predictor.predict(telemetry_window)

            prediction = {
                "anomaly_score": ml_prediction.anomaly_score,
                "fault": ml_prediction.fault,
                "confidence": ml_prediction.confidence,
                "rul_hours": ml_prediction.rul_hours,
            }

            if health is not None:
                operating_state = _twin_service._determine_operating_state(
                    health["overall"],
                    ml_prediction,
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


async def websocket_endpoint(websocket: WebSocket, engine_id: str, mission_id: str):
    await ws_manager.connect(websocket, engine_id, mission_id)
    try:
        while True:
            # Keep the connection alive; client isn't expected to send anything,
            # but we still need to await something so disconnects are detected.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, engine_id, mission_id)
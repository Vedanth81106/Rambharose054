# Rambharose054 — Aero-Piston Engine Digital Twin

An AI-enabled, real-time digital twin of a single-cylinder aero-piston (drone) engine. A Simulink model simulates the engine and its sensors. The model streams telemetry over MQTT into a time-series database, where rule-based health indices and ML models (anomaly detection, fault classification, remaining useful life) assess the engine. A live dashboard shows the engine's state and lets you inject faults while the simulation runs.

## Architecture

```
┌──────────────────────┐   engine/{id}/telemetry    ┌─────────────┐
│ Simulink model       │ ─────────────────────────► │  Mosquitto  │
│ (MATLAB -batch)      │ ◄───────────────────────── │  MQTT :1883 │
└──────────────────────┘   engine/{id}/fault        └──────┬──────┘
                                                           ▼
                                              ┌────────────────────────┐
                                              │ telemetry service      │
┌──────────────────────┐                      │ validate → store →     │
│ simulation_controller│ ◄── start / stop ──┐ │ health indices + ML    │
│ (:9000)              │                    │ └───────────┬────────────┘
└──────────────────────┘                    │             ▼
                                            │ ┌────────────────────────┐
┌──────────────────────┐  REST + WebSocket  │ │ TimescaleDB :5432      │
│ React dashboard      │ ◄────────────────► │ └───────────▲────────────┘
│ (:5173)              │                ┌───┴─────────────┴──┐
└──────────────────────┘                │ FastAPI :8000      │
                                        └────────────────────┘
```

| Component | Location | Role |
|---|---|---|
| Engine model | `simulation/AeroPistonEngineSimulator.slx`, `engine_params.m` | Engine core, fuel, thermal, lubrication, vibration, electrical and injection models with sensor dynamics and 10 fault modes |
| Stream script | `simulation/simulink_mqtt_stream.m`, `MqttLite.m` | Steps the model, publishes one telemetry message per second and applies fault commands it receives over MQTT (plain-MATLAB MQTT client, no Python needed) |
| Simulation controller | `simulation/simulation_controller.py` | Small HTTP service (Python standard library only) that finds MATLAB and starts/stops the simulation |
| Telemetry service | `backend/telemetry/` | MQTT subscriber: validates, stores, and runs the digital twin analysis |
| Digital twin | `backend/twin/` | Healthy baseline, subsystem health indices, fault and RUL predictors (trained models plug into `predictor.py`; rule-based stand-ins until then), maintenance advisory, mission reports |
| API | `backend/api/` | REST endpoints and a live WebSocket feed |
| Dashboard | `frontend/` | Live overview, mission profile selection, maintenance advisory, efficiency index, 3D engine view, fault injection, mission analysis, replay and downloadable health reports |
| Model training | `anomalyModel/`, `ai/RUL/`, `data/` | Training code and data for the ML models |

## Prerequisites

- Docker with Docker Compose
- Linux, Windows or macOS
- Docker with Compose v2 (Docker Desktop on Windows/macOS), running
- Python 3.8+ (standard library only; no packages to install)
- MATLAB R2026a or newer with Simulink (the model is saved in R2026a and won't open in older releases). The launcher finds MATLAB on `PATH` or in the default install folder; otherwise set `MATLAB_PATH` in `.env`
- Node.js, only to run the frontend outside Docker

## Getting started

1. Start everything, with the same command on every OS:

   ```bash
   python start.py          # Linux/macOS: python3 start.py, or ./start.sh
   ```

   This creates `.env` from `.env.example` if it's missing, starts Mosquitto, TimescaleDB, the telemetry service, the API and the frontend in Docker, and starts the simulation controller on the host. Database migrations run automatically when the backend containers start. The first run builds the Docker images and takes a while.

2. Open the dashboard at <http://localhost:5173>, pick a mission profile and start the simulation from there. MATLAB's output goes to `simulation/simulation.log`. You can also run the simulation directly from `simulation/` with `matlab -batch simulink_mqtt_stream` (`SIM_PROFILE` selects the profile).

3. Stop everything with `python start.py stop`.

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| API (interactive docs at `/docs`) | http://localhost:8000 |
| Simulation controller | http://localhost:9000 |

> The full stack plus MATLAB needs a fair amount of memory. On machines with about 8 GB of RAM, run only one MATLAB instance.

## Telemetry

The simulator publishes to `engine/{engine_id}/telemetry` once per second. Each message carries:
- **Engine signals:** RPM, torque, fuel flow, cylinder head and exhaust gas temperatures, oil pressure and temperature, vibration.
- **Operating conditions:** throttle, load, altitude, ambient temperature.
- **Electrical:** bus voltage, alternator current.
- **Injection:** timing and pulse width.
- **Simulation clock:** time since the run started.

The field list, units, sensor models and an example payload are in [`docs/telemetry-schema.md`](docs/telemetry-schema.md).

The architecture, its mapping to the problem statement and the known limitations are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the path to test rigs, GCS deployment and fleets is in [`docs/DEPLOYMENT_ROADMAP.md`](docs/DEPLOYMENT_ROADMAP.md). ML training guides: [`ANOMALY_MODEL_GUIDE.md`](ANOMALY_MODEL_GUIDE.md), [`RUL_MODEL_GUIDE.md`](RUL_MODEL_GUIDE.md).

## Fault modes

Faults are injected from the dashboard (or `POST /api/engines/{engine_id}/fault?fault_id=N`). Each fault grows from no effect at injection to full severity after 300 s.

| ID | Fault | What it does at full severity |
|---|---|---|
| 0 | Healthy | — |
| 1 | Misfire | Up to 35 % of combustion events miss: rough, lower RPM, lower EGT, vibration ×2 |
| 2 | Overheating | Cylinder heat input ×4: CHT, EGT and oil temperature rise |
| 3 | Oil pressure failure | Oil pressure drops to 20 %, oil temperature rises |
| 4 | Fuel starvation | Fuel flow drops to 20 %: RPM, temperatures, oil pressure and bus voltage fall |
| 5 | Injector abnormality | Injector delivers 70 % of the fuel the ECU commands |
| 6 | Cooling degradation | Cooling drops to 20 %: CHT creeps up, EGT unchanged |
| 7 | CHT sensor drift | Reported CHT reads +40 °C high and noisy; engine unaffected |
| 8 | Combustion instability | 30 % cycle-to-cycle torque variation: rough RPM |
| 9 | Abnormal vibration | Vibration ×4 (imbalance / bearing wear) |

## API overview

All REST routes are under `/api`.

| Endpoint | Purpose |
|---|---|
| `GET /engines`, `GET /engines/{id}` | Engines and their summary |
| `GET /engines/{id}/telemetry/latest` | Latest telemetry sample |
| `GET /engines/{id}/health`, `/health/history`, `/alerts` | Digital twin health state, history and alerts |
| `POST /engines/{id}/fault` | Inject a fault |
| `POST /engines/{id}/simulation/start?profile=…`, `/stop`, `GET /simulation/status` | Start a mission with a mission profile (cruise, high_altitude, hot_weather, endurance, rapid_throttle); stop; status |
| `GET /dashboard/{id}` | Everything the dashboard needs in one call |
| `GET /missions`, `/missions/{id}/telemetry`, `/missions/{id}/replay` | Mission history and replay |
| `GET /missions/{id}/report` | Mission-wise health report (outcome, faults, advisories, maintenance) |
| `GET /missions/{id}/baseline` | Expected healthy readings per sample (healthy baseline) and the derived-metric health limits, for the analysis charts |
| `DELETE /missions/{id}`, `DELETE /missions` | Permanently delete one mission or all missions (refused while a simulation is running); the analysis page's RESET DATA button |
| `WS /ws/engines/{id}?mission_id=…` | Live telemetry and health stream |

## Development

```bash
# Frontend
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # typecheck + production build

# Database migrations (run automatically on container start)
docker exec telemetry alembic upgrade head
```

In MATLAB, from `simulation/`:

```matlab
engine_params;                                            % load model parameters
r = run_telemetry_scenarios('AeroPistonEngineSimulator', 300);   % simulate every fault
check_signal_regression(baseline, candidate);             % compare two model versions
generate_ml_dataset;                                      % build the ML training dataset
```

When adding a telemetry field, update the backend schema before the simulator starts publishing it: the backend rejects unknown fields. The full checklist is in [`CLAUDE.md`](CLAUDE.md).

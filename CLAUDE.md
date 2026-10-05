# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A real-time digital twin of an aero-piston engine. A Simulink model generates engine telemetry, which flows over MQTT into TimescaleDB, gets health/ML analysis, and is shown live in a React dashboard. Faults can be injected from the dashboard while the simulation runs.

It answers the SIH 2026 problem statement in `docs/PROBLEM_STATEMENT.md` (MALE UAV aero-piston engine digital twin); `docs/ARCHITECTURE.md` §2 maps every PS requirement to the code. Check new work against the PS.

## Data flow

```
Simulink (simulation/simulink_mqtt_stream.m, MATLAB -batch)
  │ publishes 1 msg/s  ──►  MQTT engine/{engine_id}/telemetry   (mosquitto :1883)
  ▼
telemetry container (backend/telemetry/app.py)
  validate (TelemetryCreate) → store row → twin service (health indices + ML) → health_snapshots
  ▼
TimescaleDB (:5432)  ◄── api container (FastAPI, backend/api, :8000, REST under /api + WS /ws/engines/{id})
  ▼
frontend (Vite/React, :5173) — services/api.ts, hooks/useEngineData.ts

Fault injection:  dashboard → POST /api/engines/{id}/fault → MQTT engine/{id}/fault
  → simulink_mqtt_stream.m is subscribed (MqttLite.m, plain-MATLAB MQTT over tcpclient), polls each step and set_params Fault_ID + Degradation/Fault_Onset
Start/stop:  dashboard profile dropdown → POST /api/engines/{id}/simulation/start?profile=<id>
  → simulation/simulation_controller.py (:9000) creates mission_<UTC date>_<time>_<profile>
  → matlab -batch simulink_mqtt_stream (output in simulation/simulation.log), with SIM_PROFILE / SIM_MISSION_ID env vars
```

The simulator is not a container: the simulation controller runs on the host (`start.py` launches it detached) and spawns its own batch MATLAB process. Everything host-side must stay cross-platform (Linux and Windows): `start.py` and the controller use only the Python standard library, MATLAB is found via `MATLAB_PATH` (.env) → PATH → default install folders, and MATLAB needs no Python (no paho/pyenv).

## Commands

```bash
python3 start.py                             # docker compose up -d + simulation controller (same on Windows: python start.py)
python3 start.py stop                        # stop simulation, controller and containers
docker compose up -d mosquitto timescaledb telemetry api   # backend only (skip the frontend container)

# Frontend (frontend/)
npm run dev                                  # Vite on :5173
npm run build                                # tsc -b && vite build; tsc has noUnusedLocals, so dead code fails the build
npx tsc -b --noEmit                          # typecheck only

# Database migrations (Alembic, backend/telemetry/migrations). The entrypoint runs `alembic upgrade head` on container start.
docker exec telemetry alembic current
docker exec telemetry alembic upgrade head
```

There is no backend test suite and no linter config. Verify backend changes by publishing a payload and reading it back:

```bash
docker exec mosquitto mosquitto_pub -t engine/engine_verify/telemetry -m '{...}'   # see docs/telemetry-schema.md for an example payload
curl "localhost:8000/api/engines/engine_verify/telemetry/latest?mission_id=..."
```

Delete such test rows afterwards from `telemetry`, `health_snapshots` and `ingestion_events`. The telemetry table's time column is `time`, not `timestamp`.

### Simulink checks (run in MATLAB, from simulation/)

```matlab
engine_params;                                              % loads all model parameters into the base workspace; required before sim
set_param('AeroPistonEngineSimulator','SimulationCommand','update')   % compile check
r = run_telemetry_scenarios('AeroPistonEngineSimulator', 300, {'steady'}, 0:9);  % one sim per Fault_ID
report = check_signal_regression(baseline, candidate);      % prove a model edit left signals 1-9 bit-identical
```

The ML dataset (`data/sim_v2/`, git-ignored) comes from `generate_sim_dataset('../data/sim_v2', seeds)` (resumable; skips runs that crash MATLAB), then `python ai/dataset/label_dataset.py data/sim_v2` and `python ai/dataset/check_dataset.py data/sim_v2`. Long MATLAB jobs: track progress by watching output files; MCP calls silent for 30 min are aborted while MATLAB keeps running.

## Things that span multiple files

- **Adding a telemetry field** touches, in order: `backend/telemetry/schemas.py` (TelemetryCreate uses `extra="forbid"`, so the backend must accept the field *before* the publisher sends it), `models.py`, a new Alembic migration (nullable column, so old rows stay valid), `repository.py`, `service.py`, `backend/api/schemas.py` (`TelemetryResponse.from_row`, which also feeds the WebSocket), `frontend/src/types/api.ts`, `ZERO_TELEMETRY` in `frontend/src/hooks/useEngineData.ts`, the `sprintf` in `simulation/simulink_mqtt_stream.m`, and `docs/telemetry-schema.md`.
- **Predictors (`backend/twin/predictor.py`).** The twin calls a `FaultModel` and a `RULModel` once per sample with up to 300 samples of dataset-shaped dicts (signals, flight conditions, `expected_*`, `health_*`; see `ANOMALY_MODEL_GUIDE.md` §6.1). `create_predictors()` returns the trained models, each falling back to its rule-based stand-in (`RuleFaultModel`, `HealthTrendRULModel`) if it can't load:
  - `XGBoostFaultModel`: an XGBoost classifier (`ml_models/fault/xgboost_classifier.json`, which fault) plus a dense autoencoder (`ml_models/fault/autoencoder.json`, run with numpy; anything wrong), both on the 32 features of `twin/fault_features.py`, an exact copy of `anomaly-model-new/v2/fault_features.py`, which trained them. Keep the two identical. Anomaly = classifier ≥ 90 % sure of a fault, or the autoencoder alarms (5 of the last 10 scores over threshold); an alarm the classifier can't name is "unclassified". Anomaly score = autoencoder median score / threshold.
  - `GRURULModel`: `ml_models/rul_gru/` (ONNX + scaler, run with onnxruntime, no PyTorch) on `twin/rul_features.py`, an exact copy of `rul-model-new/rul/rul_features.py`, which trained it. Keep the two identical.
  - In the service, the RUL is held at the cap unless the fault model reports an anomaly (hides false countdowns), and set to 0 once the failure definition is met.

  Predictions, operating state and the maintenance advisory (`backend/twin/advisory.py` + `advisory_rules.json`) are computed once per sample in the telemetry service and stored on the health snapshot; the API and WebSocket only read snapshots. Anomaly scores are normalised (1.0 = threshold); RUL is in seconds, capped at 600.
- **Rule-based health limits in `backend/twin/service.py` mirror Simulink parameters** in `simulation/engine_params.m` (`elec.*`, `inj.*`, the injection timing map). Change both together.
- **Faults.** `Fault_ID` 0–9 selects rows of 2-D lookup tables (fault ID × degradation) spread across the model's subsystems. Degradation ramps 0→1 over `fault_ramp_time` (300 s) from `Degradation/Fault_Onset`, so a freshly injected fault has no effect yet. The fault list and signatures are documented in `docs/telemetry-schema.md` and must be kept in sync with the valid fault IDs in `backend/api/routers/engines.py`, `simulink_mqtt_stream.m`, and the health indices.
- **Failure definition** (`backend/twin/failure.py`): the engine has failed when the weakest engine subsystem health (sensor health excluded), averaged over 90 s, drops below 30 and stays there. RUL labels come from the same `calculate_health()` the live twin uses. The penalty scales in `backend/twin/service.py` are calibrated so every fault fails, and a healthy cruise run never does. After changing them or the fault tables, re-run a fault sweep through the health code.
- **Mission profiles and the healthy baseline.** `simulation/mission_profile.m` defines the five profiles (cruise, high_altitude, hot_weather, endurance, rapid_throttle) as throttle/load/altitude/ambient input matrices. Without a seed it returns the nominal values (cruise nominal = the original live inputs); with a seed it randomises them for datasets. Ambient is the air temperature at altitude (ISA lapse). Because healthy readings differ per profile, the health limits in `service.py` are cruise limits shifted by `expected − CRUISE_REFERENCE`. `expected` comes from `backend/twin/baseline.py`, a ridge regression on lagged operating-condition features whose coefficients are in `backend/twin/ml_models/baseline/healthy_baseline.json`. Refit it with `python ai/baseline/fit_baseline.py <dir of healthy 1 Hz CSVs from engine start>` after changing the model's healthy behaviour. The live twin fetches up to `HISTORY_SAMPLES` (1200) samples per message for the lags.
- **Sensor chain.** Every published signal passes lag → drift ramp → noise → ZOH → saturation, so reported values can clip. For example, oil temperature saturates at 200 °C, and vibration ratios read lower than the model multipliers because of the additive drift.
- `signal7` in `telemetry_log` is the Fault_ID ground-truth label: it is logged for datasets and never published.

## Environment constraints

- The machine has 7.5 GB RAM. The MATLAB desktop plus the api and telemetry containers can OOM. Prefer a single MATLAB process: don't start another MATLAB while the controller's batch simulation is running.
- `backend/` is bind-mounted into the containers, which run as root, so `__pycache__` dirs on the host are root-owned. Use `ast.parse` rather than `py_compile` for host-side syntax checks.
- The frontend container keeps `node_modules` in the named volume `frontend_node_modules`. After adding a dependency, rebuild the image and recreate that volume, or the container won't see the dependency.
- Only use files inside this repo; don't pull inputs from `~/Downloads` or elsewhere.
- Credentials come from `.env` (template: `.env.example`).

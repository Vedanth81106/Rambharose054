# Telemetry Schema v2

Live engine telemetry published by the Simulink simulator
(`simulation/simulink_mqtt_stream.m`) and ingested by the backend
(`backend/telemetry/schemas.py:TelemetryCreate`).

## MQTT Topic

```
engine/{engine_id}/telemetry
```

Example: `engine/engine_001/telemetry` (QoS 1, one message per second).

The `engine_id` in the topic must match the payload. Unknown fields are
rejected (`extra="forbid"`), so the backend schema must be updated
**before** a publisher adds a new field.

## Payload

| Field | Type | Unit | Required | Simulink source (`telemetry_log`) | Description |
|---|---|---|---|---|---|
| timestamp | string | ISO-8601 UTC | Yes | — | Wall-clock publish time; must include a timezone |
| engine_id | string | — | Yes | — | Engine identifier (must match the topic) |
| mission_id | string | — | Yes | — | Mission identifier |
| rpm | float | RPM | Yes | signal1 (`Subsystem1`) | Engine speed |
| fuel_flow | float | kg/h | Yes | signal2 (`Subsystem5`) | Fuel mass flow |
| torque | float | N·m | Yes | signal3 (`Subsystem2`) | Engine brake torque |
| oil_temperature | float | °C | Yes | signal4 (`Subsystem7`) | Oil temperature |
| oil_pressure | float | psi | Yes | signal5 (`Subsystem6`) | Oil pressure |
| cht | float | °C | Yes | signal6 (`Subsystem3`) | Cylinder head temperature |
| egt | float | °C | Yes | signal8 (`Subsystem4`) | Exhaust gas temperature |
| vibration | float | model units | Yes | signal9 (`Subsystem8`) | Crank-synchronous vibration amplitude + noise |
| throttle | float | 0–1 | Yes | model input 1 | Throttle position |
| engine_load | float | 0–1 | Yes | model input 2 | Normalised external load |
| altitude | float | m | Yes | model input 3 | Pressure altitude |
| ambient_temperature | float | °C | Yes | model input 4 | Outside air temperature |
| battery_voltage | float | V | No | signal10 (`Sensor_BatteryVoltage`) | 28 VDC bus / battery terminal voltage |
| alternator_current | float | A | No | signal11 (`Sensor_AlternatorCurrent`) | Alternator output current |
| injection_timing | float | ° BTDC | No | signal12 (`Sensor_InjectionTiming`) | Start of injection, crank degrees before top dead centre |
| injection_duration | float | ms | No | signal13 (`Sensor_InjectionDuration`) | Injector pulse width per injection event |
| sim_time | float | s | No | simulation clock (`simulink_mqtt_stream.m`) | Simulation time since the run started; fault onset and progression are timed on it. Shown as the dashboard TIME field |

`signal7` is the `Fault_ID` ground-truth label. It is logged by Simulink for
dataset generation only and is **not** published.

The four electrical/injection fields are optional so older publishers and
telemetry recorded before they existed remain valid; they are stored as
nullable columns and returned as `null` for such rows. The current simulator
always publishes them.

## Electrical system (`Electrical_Model`)

Input: true engine speed (`EngineCore` RPM). Parameters: `elec.*` in
`simulation/engine_params.m`. Read-only: no alternator torque is fed back
into `EngineCore`.

- Alternator capacity rises linearly from 0 A at `RPM_alt_cutin` (1200 RPM)
  to `I_alt_max` (25 A) at `RPM_alt_rated` (3500 RPM).
- Demand = avionics load `I_avionics` (10 A) + battery charge acceptance
  (up to `I_charge_max` = 5 A, tapering to 0 above 95 % state of charge).
- `alternator_current = min(capacity, demand)`.
- Battery state of charge integrates `(alternator_current − I_avionics)`
  over a 7 Ah battery.
- `battery_voltage` is held at the regulator set point `V_bus_reg`
  (28.0 V) while the alternator carries the full demand, and sags toward the
  battery open-circuit voltage (22.0–25.6 V by state of charge) minus the
  internal-resistance drop when it cannot (e.g. low RPM).

Typical values: healthy cruise 28.0 V / 10–15 A; fuel starvation
(Fault 4, low RPM) ≈ 24.5–24.7 V / < 4 A.

## Injection parameters (`Injection_Model`)

Read-only ECU parameters; they do not feed back into combustion physics.
Parameters: `inj.*` in `simulation/engine_params.m`.

**`injection_timing`** — start of injection in crank degrees BTDC
(positive = before top dead centre), from the 2-D map
`inj.timing_table` indexed by engine speed and throttle (linear
interpolation, clipped at the map edges):

| RPM \ throttle | 0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| 1500 | 12 | 11 | 10 | 9 | 8 |
| 3000 | 16 | 15 | 14 | 13 | 12 |
| 4500 | 20 | 19 | 18 | 17 | 16 |
| 6000 | 23 | 22 | 21 | 20 | 19 |
| 7500 | 26 | 25 | 24 | 23 | 22 |

**`injection_duration`** — injector pulse width per injection event (ms),
from fuel flow (kg/h) and engine speed:

```
events_per_s  = n_cyl · RPM / (60 · strokes/2)          (1 cyl, 4-stroke)
fuel_per_event = fuel_flow · 1000/3600 / events_per_s     (g)
duration_ms    = 1000 · fuel_per_event / q_static_gps + t_dead_ms
               (q_static_gps = 2.5 g/s, t_dead_ms = 0.8 ms,
                capped at one engine cycle, 0 below 300 RPM)
```

Typical values at the 4000 RPM / full-throttle cruise point:
≈ 14.7 ° BTDC and ≈ 10.5 ms.

## Sensor conditioning

Every published model output passes through the same sensor chain:
first-order lag → drift ramp → band-limited white noise → zero-order hold →
saturation. Signals 10–13 use a discrete first-order lag at the 10 Hz
telemetry rate (`Ts_telemetry_std`), so they leave the solver's continuous
states — and therefore signals 1–9 — bit-identical to the original model.

| Field | Lag τ | Noise σ | Range |
|---|---|---|---|
| battery_voltage | 0.10 s | ≈ 0.05 V | 0–36 V |
| alternator_current | 0.10 s | ≈ 0.2 A | 0–40 A |
| injection_timing | 0.05 s | ≈ 0.1 ° | 0–60 ° BTDC |
| injection_duration | 0.05 s | ≈ 0.02 ms | 0–30 ms |

## Example Payload

```json
{
  "timestamp": "2026-10-02T16:00:00.123Z",
  "engine_id": "engine_001",
  "mission_id": "mission_001",
  "rpm": 3994.712,
  "torque": 9.998,
  "cht": 81.402,
  "egt": 712.551,
  "oil_pressure": 61.287,
  "oil_temperature": 107.811,
  "fuel_flow": 3.142,
  "vibration": 1.812,
  "throttle": 1.000,
  "engine_load": 0.500,
  "altitude": 0.000,
  "ambient_temperature": 25.000,
  "battery_voltage": 28.012,
  "alternator_current": 14.987,
  "injection_timing": 14.651,
  "injection_duration": 10.472,
  "sim_time": 412.0
}
```

## Downstream use

| Layer | Uses the new fields? |
|---|---|
| Database (`telemetry` table) | Stored as nullable `FLOAT` columns (migration `7c2e9a41b5d3`) |
| ML (autoencoder, XGBoost, RUL GRU) | **No.** Models receive exactly their original feature sets |
| Digital Twin health | `battery_voltage` + `alternator_current` → `health.electrical`; `injection_timing` + `injection_duration` → `health.injection` (median signed mismatch between the fuel flow the ECU pulse commands and the measured fuel flow, plus timing vs. the ECU map). Both rule-based and part of `health.overall` (the weakest engine subsystem) when present. `health.sensor` (CHT jitter) is reported but kept out of `health.overall`; every subsystem drives the operating state |
| API / WebSocket | Returned in every telemetry object (`latest`, dashboard, mission telemetry, replay, WebSocket) |

## Simulated faults (`Fault_ID`)

Every fault grows from no effect at injection to full severity after
`fault_ramp_time` (300 s, `simulation/engine_params.m`). The live stream
restarts the progression at each injection (`Degradation/Fault_Onset`).

| ID | Fault | Main signature | Rule-based health index |
|---|---|---|---|
| 0 | Healthy | — | — |
| 1 | Misfire | Intermittent missed combustion events (up to 35 % of 50 ms windows produce no torque): rough RPM, RPM ↓, EGT ↓, vibration ×2; fuel flow follows RPM | combustion (RPM drop + roughness), mechanical (mild) |
| 2 | Overheating | Heat input ×4: CHT, EGT, oil temp ↑ | thermal |
| 3 | Oil pressure failure | Oil pressure → 20 %, oil temp ↑ | lubrication |
| 4 | Fuel starvation | Fuel → 20 %, RPM ↓↓, CHT/EGT ↓, oil pressure ↓ (with RPM), bus voltage ↓; oil temperature stays normal | combustion, lubrication, electrical |
| 5 | Injector abnormality | Delivered fuel → 70 % of commanded; ECU pulse unchanged | injection |
| 6 | Cooling degradation | Cooling → 20 %: CHT creeps up, EGT unchanged | thermal |
| 7 | CHT sensor drift/failure | Reported CHT +40 °C and erratic (σ 6 °C); engine unaffected | sensor |
| 8 | Combustion instability | Cycle-to-cycle torque variation (σ 30 %): rough RPM | combustion (RPM roughness) |
| 9 | Abnormal vibration | Vibration amplitude ×4 (imbalance / bearing wear) | mechanical (vibration RMS) |

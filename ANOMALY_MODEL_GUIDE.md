# Anomaly Detection & Fault Identification — Training Guide

This guide is for whoever trains the anomaly / fault model of the aero-piston engine digital twin. It covers what the model must do for the SIH problem statement, how the simulated engine and its faults behave, the dataset, which algorithms to use, how to evaluate, and how to hand the model back so the live system can run it.

The RUL (remaining useful life) model has its own guide. The two models share the same dataset.

All numbers below were measured from the Simulink model the dataset was generated with (commit `c6764ed`, October 2026). They are simulator values, not certified engine limits.

---

## 1. What the model has to do

The problem statement asks the system to move from threshold alarms to predictive diagnostics. That means it must:

- detect abnormal operating conditions;
- detect and identify misfire, injector abnormalities, cooling degradation, lubrication issues, sensor drift/failure, combustion instability, overheating trends and abnormal vibration;
- **predict probable failures before they occur.**

For this model, "before they occur" means:

> Every fault in the simulator starts invisible and grows over several minutes until the engine fails (a subsystem's health stays below 30/100). **Your model must raise the alarm, and name the right fault, while the fault is still small — long before failure.**

So the most important number you report is **lead time**: how many seconds before failure the model correctly identified the fault. A model that only recognises fully developed faults scores high on accuracy but is useless for the PS.

The job splits into two parts:

| Part | Question | Output |
|---|---|---|
| **A. Anomaly detector** | Is the engine behaving differently from a healthy engine in the same flight conditions? | Anomaly score + anomalous yes/no |
| **B. Fault classifier** | Which of the 9 faults is developing? | Fault ID (0 = healthy, 1–9) + confidence |

Part A also catches problems the classifier was never trained on. Part B makes the alarm actionable.

---

## 2. The engine and the simulator

- **Engine:** a single-cylinder, four-stroke, naturally aspirated ~100 cc aero-piston engine with electronic fuel injection, a 28 V electrical system and an alternator. It's modelled in Simulink (`simulation/AeroPistonEngineSimulator.slx`, parameters in `simulation/engine_params.m`).
- **Physics:**
  - Torque scales with throttle × air density. Air density follows the standard atmosphere, so the engine loses about half its power at 6 km.
  - CHT and oil temperature come from heat balances, so they lag power changes by minutes.
  - Oil pressure follows RPM and oil temperature.
  - The alternator only carries the 10 A avionics load above ~2600 RPM. Below that, the bus drops to battery voltage (~26 V).
- **Sensors:** every signal passes through a realistic sensor chain: lag → slow drift → noise → sampling → range limits. So expect noise, and some signals clip at their range limits.
- **Live system:** Simulink publishes one sample per second over MQTT. The backend stores it, computes health, and calls your model. **Train at 1 Hz.**
- **Time scale:** compressed. Real faults develop over hours; here they develop over 1–15 minutes, so a whole fault fits into a demo. Say so if judges ask.

### 2.1 Inputs the engine receives (flight conditions)

These four come from the mission profile. They are **causes**, not symptoms:

| Field | Unit | Meaning |
|---|---|---|
| `throttle` | 0–1 | Throttle position |
| `engine_load` | 0–1 | Propeller / payload load on the engine |
| `altitude` | m | Altitude above sea level |
| `ambient_temperature` | °C | Outside air temperature **at the aircraft's altitude** (drops ~6.5 °C per km climbed) |

### 2.2 Signals the engine produces (12)

| Field | Unit | Notes |
|---|---|---|
| `rpm` | RPM | Engine speed. Very low noise when healthy (±0.5 RPM), so any jitter means something |
| `torque` | N·m | Very noisy (healthy cruise 8.7–12.0 N·m). Average over windows |
| `fuel_flow` | kg/h | Fuel actually delivered |
| `cht` | °C | Cylinder head temperature. Slow; noise ~±1 °C |
| `egt` | °C | Exhaust gas temperature. Fast |
| `oil_pressure` | psi | Follows RPM |
| `oil_temperature` | °C | Slow; sensor range 0–200 °C (can saturate at 200 in severe oil pressure failure, see §9) |
| `vibration` | model units | A sampled **oscillation** around 0 (±2.5). Its mean is meaningless, so **use its RMS over a window** (healthy ≈ 1.5) |
| `battery_voltage` | V | 28 V bus. Healthy 27.9–28.1, unless at low RPM (see above) |
| `alternator_current` | A | Wanders 10–15 A when healthy (battery charging) |
| `injection_timing` | ° BTDC | ECU start-of-injection, from an RPM × throttle map |
| `injection_duration` | ms | ECU injector pulse width. It tells you how much fuel the ECU *commanded* (§5.3) |

---

## 3. Mission profiles: how the drone flies and what a healthy engine reads

`simulation/mission_profile.m` defines five profiles, the conditions the PS asks for. Each has a nominal version, used by the live demo, and random variations, used in the dataset.

| Profile | What the drone does | Dataset variation range |
|---|---|---|
| **Cruise** | Steady level flight | Throttle 70–100 %, load 40–60 %, altitude 0–1500 m, ground temperature 10–35 °C |
| **High altitude** | Full-throttle climb, then cruise at altitude in thin, cold air | Target 3000–7500 m, climb at 3–8 m/s, cruise throttle 70–95 % |
| **Hot weather** | Low-altitude flight on a hot day | Ground temperature 40–50 °C, altitude 0–1500 m |
| **Endurance** | Long loiter at medium altitude; power, load and altitude drift slowly | 2000–4500 m, throttle 60–85 % ± 5 % |
| **Rapid throttle** | Throttle steps between low and high power every 15–45 s, each step taking 1–3 s | Low 30–50 %, high 85–100 % |

### 3.1 Healthy engine readings per profile

Nominal profiles, after warm-up. These are 5th–95th percentile ranges:

| Signal | Cruise | High altitude (climb to 4500 m) | Hot weather (45 °C) | Endurance (~3000 m) | Rapid throttle |
|---|---|---|---|---|---|
| Throttle | 100 % | 85–100 % | 100 % | 70–80 % | 40–100 % |
| Altitude (m) | 0 | 1044–4500 | 500 | 2700–3300 | 500 |
| Ambient (°C) | 25 | −4 to 18 | 42 | 4–7 | 22 |
| RPM | 3993–3994 | 2830–3779 | 3742–3743 | 2743–3034 | 2315–3891 |
| Torque (N·m) | 8.7–12.0 | 5.0–9.7 | 7.7–10.9 | 4.2–7.7 | 3.1–11.0 |
| Fuel flow (kg/h) | 2.74–3.05 | 1.12–2.54 | 2.32–2.63 | 1.11–1.53 | 0.84–2.82 |
| CHT (°C) | 78.6–81.3 | 29–70 | 95.2–98.2 | 33.9–41.0 | 63.3–69.4 |
| EGT (°C) | 707–711 | 371–636 | 653–657 | 366–416 | 330–674 |
| Oil pressure (psi) | 58.3–60.6 | 41.0–56.6 | 54.5–56.8 | 40.4–45.3 | 33.5–58.7 |
| Oil temperature (°C) | 104.0–107.3 | 75.5–98.9 | 128.8–132.0 | 70.6–85.6 | 100.8–104.0 |
| Vibration RMS | ~1.5 | ~1.5 | ~1.5 | ~1.5 | ~1.5 |
| Bus voltage (V) | 27.9–28.1 | 27.9–28.1 | 27.9–28.1 | 27.9–28.1 | **25.3**–28.1 |
| Injection timing (°) | 14.5–14.8 | 12.0–14.1 | 13.8–14.1 | 12.4–13.0 | 12.4–14.5 |
| Injection duration (ms) | 10.4–10.5 | 6.6–9.7 | 9.6–9.7 | 6.6–7.2 | 6.3–10.2 |

**The key lesson:** a healthy engine at high altitude reads 2800 RPM and a 30 °C CHT. A healthy engine on a hot day reads 130 °C oil. If you train on raw values, the model will call healthy flights faulty and miss real faults. **You must compare against what a healthy engine should read in the same conditions** (§5.1).

Other things to know:
- **Warm-up:** the first 2–5 minutes of every run are an engine warm-up from cold (CHT and oil from 25 °C). That's normal, not a fault. The backend only starts scoring at the 60th sample.
- **Low CHT at altitude:** in cold, high, low-power flight, CHT can sit at 6–40 °C. That's a simulator quirk (its CHT scale runs low), but it's consistent, so the model can learn it.
- **Rapid throttle:** RPM swings 2300 ↔ 3900 and EGT swings 330 ↔ 670 °C every few tens of seconds while healthy. This profile is the false-alarm stress test.

---

## 4. The faults

### 4.1 How a fault unfolds

1. **Injection:** a fault is switched on at an *onset* time. At that moment it has **zero effect**.
2. **Ramp:** its strength (`severity`) grows linearly from 0 to 1 over a *ramp time*, then stays at 1.
3. **Failure:** at some point the weakest engine subsystem's health (0–100, computed by the backend from the signals, averaged over 90 s) drops below 30 and stays there. That moment is labelled failure (`backend/twin/failure.py`). Sensor health doesn't count: a broken sensor isn't a broken engine.

The dataset uses different ramp times per fault, so faults that are dangerous in reality also develop quickly here:

| Speed | Faults | Ramp time |
|---|---|---|
| Fast | 3 oil pressure, 4 fuel starvation | 1–3 min |
| Medium | 1 misfire, 2 overheating | 3–6 min |
| Slow | 5 injector, 6 cooling, 7 CHT sensor, 8 instability, 9 vibration | 8–15 min |

### 4.2 What each fault does, at full strength

| ID | Fault | What physically happens (model) | PS category |
|---|---|---|---|
| 0 | Healthy | — | — |
| 1 | Misfire | Up to 35 % of 50 ms combustion windows produce no torque; engine vibration ×2 | Misfire conditions |
| 2 | Overheating | Combustion heat into the head ×4, EGT +300 °C, oil heat ×1.5 | Overheating trends |
| 3 | Oil pressure failure | Oil pressure ×0.2; oil heat ×2 | Lubrication issues |
| 4 | Fuel starvation | Fuel flow and torque ×0.2 | (extra) |
| 5 | Injector abnormality | Injector delivers 70 % of the fuel the ECU commands; torque ×0.84 | Injector abnormalities |
| 6 | Cooling degradation | Head cooling ×0.2; oil heat ×1.3 | Cooling degradation |
| 7 | CHT sensor drift/failure | **Sensor only:** reported CHT +40 °C, plus noise σ 6 °C. The engine is unaffected and the engine never "fails" | Sensor drift/failure |
| 8 | Combustion instability | Cycle-to-cycle torque variation σ 30 %; torque ×0.96 | Combustion instability |
| 9 | Abnormal vibration | Vibration ×4 (imbalance / bearing wear); torque ×0.98 | Abnormal vibration patterns |

### 4.3 How each fault degrades the signals: early, mid and full strength

Measured at cruise (full throttle, sea level, 25 °C), fault injected at 120 s with a 5-minute ramp. Values are window averages:

- **Strength windows:** 25 % = 180–210 s, 50 % = 255–285 s, 100 % = 540–600 s.
- **Healthy row:** a healthy run over the 100 % window.
- **Bold:** clearly different from a healthy run at the same moment. The thresholds sit above normal noise: RPM ±0.5 %, torque ±5 %, vibration RMS +25 %, roughness ×2, everything else ±3 %.

How the derived columns are computed:

- **Fuel ratio** = measured ÷ commanded fuel (§5.3).
- **Vib RMS** = root-mean-square of the vibration signal.
- **Roughness** = median |x[i] − (x[i−1]+x[i+1])/2| over the window. Healthy RPM roughness is ≈ 0.2–0.4, healthy CHT roughness ≈ 0.5–0.8.

| Fault | Strength | RPM | Torque (N·m) | Fuel (kg/h) | Fuel ratio | CHT (°C) | EGT (°C) | Oil P (psi) | Oil T (°C) | Bus (V) | Inj pulse (ms) | Vib RMS | RPM rough | CHT rough |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **0 Healthy** | — | 3994 | 10.4 | 2.89 | 1.00 | 80 | 709 | 59.3 | 106 | 28.0 | 10.47 | 1.35 | 0.3 | 0.71 |
| 1 Misfire | 25 % | **3796** | **8.8** | **2.79** | 1.00 | 80 | **684** | **56.5** | 105 | 28.0 | 10.64 | **1.90** | **51.8** | 1.03 |
|  | 50 % | **3591** | **8.2** | **2.72** | 1.01 | 81 | **662** | **53.5** | 105 | 28.0 | **10.83** | 2.07 | **78.7** | 0.67 |
|  | 100 % | **3195** | **7.1** | **2.51** | 1.00 | **85** | **612** | **47.4** | 106 | 28.0 | **11.27** | **2.24** | **69.0** | 0.71 |
| 2 Overheating | 25 % | 3994 | 9.7 | 2.89 | 1.00 | **101** | **782** | 59.5 | **114** | 28.0 | 10.47 | 1.48 | 0.3 | 1.03 |
|  | 50 % | 3994 | 9.9 | 2.92 | 1.01 | **139** | **857** | 59.5 | **124** | 28.0 | 10.47 | 1.91 | 0.3 | 0.67 |
|  | 100 % | 3994 | 10.4 | 2.89 | 1.00 | **243** | **1009** | 59.3 | **146** | 28.0 | 10.47 | 1.35 | 0.3 | 0.71 |
| 3 Oil pressure | 25 % | 3994 | 9.7 | 2.89 | 1.00 | 79 | 709 | **47.6** | **122** | 28.0 | 10.47 | 1.48 | 0.3 | 1.03 |
|  | 50 % | 3994 | 9.9 | 2.92 | 1.01 | 80 | 709 | **35.7** | **142** | 28.0 | 10.47 | 1.91 | 0.3 | 0.67 |
|  | 100 % | 3994 | 10.4 | 2.89 | 1.00 | 80 | 709 | **11.5** | **186** | 28.0 | 10.47 | 1.35 | 0.3 | 0.71 |
| 4 Fuel starvation | 25 % | **3549** | **7.8** | **2.14** | 1.00 | **75** | **578** | **52.8** | 105 | 28.0 | **8.87** | 1.63 | 0.3 | 1.03 |
|  | 50 % | **3030** | **6.1** | **1.48** | 1.01 | **67** | **449** | **45.1** | 105 | 28.0 | **7.23** | 1.89 | 0.3 | 0.67 |
|  | 100 % | **1524** | **2.7** | **0.29** | 0.97 | **42** | **195** | **22.4** | 106 | **24.8** | **3.36** | 1.25 | 0.3 | 0.71 |
| 5 Injector | 25 % | **3909** | 9.3 | **2.62** | **0.92** | 77 | **666** | 58.2 | 105 | 28.0 | 10.54 | 1.77 | 0.3 | 1.03 |
|  | 50 % | **3820** | **9.2** | **2.41** | **0.86** | **74** | **626** | **56.9** | 105 | 28.0 | 10.62 | 2.01 | 0.3 | 0.67 |
|  | 100 % | **3633** | **8.8** | **1.90** | **0.70** | **65** | **542** | **53.9** | 106 | 28.0 | **10.79** | 1.35 | 0.3 | 0.71 |
| 6 Cooling | 25 % | 3994 | 9.7 | 2.89 | 1.00 | **86** | 709 | 59.5 | **110** | 28.0 | 10.47 | 1.48 | 0.3 | 1.03 |
|  | 50 % | 3994 | 9.9 | 2.92 | 1.01 | **100** | 709 | 59.5 | **116** | 28.0 | 10.47 | 1.91 | 0.3 | 0.67 |
|  | 100 % | 3994 | 10.4 | 2.89 | 1.00 | **236** | 709 | 59.3 | **130** | 28.0 | 10.47 | 1.35 | 0.3 | 0.71 |
| 7 CHT sensor | 25 % | 3994 | 9.7 | 2.89 | 1.00 | **89** | 709 | 59.5 | 105 | 28.0 | 10.47 | 1.48 | 0.3 | 0.81 |
|  | 50 % | 3994 | 9.9 | 2.92 | 1.01 | **101** | 709 | 59.5 | 105 | 28.0 | 10.47 | 1.91 | 0.3 | **2.37** |
|  | 100 % | 3994 | 10.4 | 2.89 | 1.00 | **120** | 709 | 59.3 | 106 | 28.0 | 10.47 | 1.35 | 0.3 | **4.33** |
| 8 Instability | 25 % | 3979 | 9.6 | 2.88 | 1.00 | 79 | 707 | 59.3 | 105 | 28.0 | 10.48 | 1.75 | **15.1** | 1.03 |
|  | 50 % | **3950** | 9.7 | 2.89 | 1.01 | 80 | 704 | 58.8 | 105 | 28.0 | 10.51 | 1.78 | **24.5** | 0.67 |
|  | 100 % | **3905** | 10.0 | 2.85 | 1.00 | 80 | 698 | 58.0 | 106 | 28.0 | 10.54 | 1.37 | **58.4** | 0.71 |
| 9 Vibration | 25 % | 3983 | 9.7 | 2.88 | 1.00 | 79 | 708 | 59.3 | 105 | 28.0 | 10.48 | 1.79 | 0.3 | 1.03 |
|  | 50 % | **3973** | 9.8 | 2.91 | 1.01 | 80 | 707 | 59.2 | 105 | 28.0 | 10.49 | **2.92** | 0.3 | 0.67 |
|  | 100 % | **3951** | 10.2 | 2.87 | 1.00 | 80 | 703 | 58.7 | 106 | 28.0 | 10.50 | **4.23** | 0.3 | 0.71 |

**What to look for first (the early, 25 % signature):**

| Fault | First clear sign | Also changes | Stays normal |
|---|---|---|---|
| 1 Misfire | RPM roughness ×150 | RPM, EGT, oil pressure ↓; vibration ↑ | CHT, oil temperature, fuel ratio |
| 2 Overheating | CHT +21 °C | EGT ↑, oil temperature ↑ | RPM, fuel, oil pressure |
| 3 Oil pressure | Oil pressure −20 % | Oil temperature ↑ | Everything else |
| 4 Fuel starvation | Fuel −25 %, RPM −11 % | EGT, CHT, oil pressure, injector pulse ↓ | Fuel ratio (≈1: the ECU commands less fuel too) |
| 5 Injector | Fuel ratio 0.99 → 0.92 | Fuel, EGT ↓; injector pulse slowly ↑ | Bus voltage |
| 6 Cooling | CHT +6 °C, oil temperature +5 °C | — | **EGT** (separates it from overheating) |
| 7 CHT sensor | CHT +10 °C | CHT roughness ↑ (clear from 50 %) | **EGT, oil temperature** (the engine is fine) |
| 8 Instability | RPM roughness ×50 | — | Average RPM, EGT, vibration |
| 9 Vibration | Vibration RMS +20 % (noisy over 30 s; ×2 by 50 %) | — | Everything else |

Every fault is visible by 25 % strength, if you look at the right feature. That's what makes early detection achievable.

### 4.4 When the engine fails (time from injection)

Health replay with a 5-minute ramp; the percentage is the fault strength at failure:

| Fault | Cruise | Endurance (low power) |
|---|---|---|
| 1 Misfire | 98 s (33 %) | 118 s (39 %) |
| 2 Overheating | 167 s (56 %) | 210 s (70 %) |
| 3 Oil pressure | 182 s (61 %) | 218 s (73 %) |
| 4 Fuel starvation | 258 s (86 %) | 315 s (after full strength) |
| 5 Injector | 264 s (88 %) | 437 s (after full strength) |
| 6 Cooling | 314 s (after full strength) | 440 s (after full strength) |
| 7 CHT sensor | never | never |
| 8 Instability | 165 s (55 %) | 296 s (99 %) |
| 9 Vibration | 326 s (after full strength) | 334 s (after full strength) |

At low power, faults fail later: up to 70 % later than at cruise, and several only after reaching full strength, because there's less heat to shed and less vibration at lower RPM. Every engine fault still reaches failure; only the sensor fault (7) never counts as engine failure.

### 4.5 Pairs that are hard to tell apart, and what separates them

| Confusable | Separating feature |
|---|---|
| 4 Fuel starvation (early) vs 5 Injector | **Measured ÷ commanded fuel** (§5.3): healthy 0.99, fuel starvation 0.94, injector **0.69**. Also bus voltage falls only with fuel starvation |
| 1 Misfire vs 8 Instability | Both make RPM rough. Misfire also drops mean RPM, EGT and oil pressure and raises vibration; instability barely moves averages |
| 2 Overheating vs 6 Cooling vs 7 Sensor | All raise CHT. Overheating also raises **EGT**; cooling raises **oil temperature** but not EGT; the sensor fault raises **CHT roughness** and nothing else |
| 9 Vibration vs 1 Misfire | Both raise vibration RMS. Misfire also has RPM roughness and RPM drop |
| Any fault vs a healthy flight transient | Residuals (§5.1). During rapid throttle, raw RPM and EGT swing more than many faults do |

---

## 5. Features

### 5.1 Residuals: the most important idea

For each signal the backend has an **expected healthy value** from a baseline model that knows the flight conditions (`backend/twin/baseline.py`). It predicts RPM, EGT, CHT, oil pressure, oil temperature, bus voltage and alternator current. Its held-out accuracy (RMSE / 99th-percentile error) is:

| Signal | RPM | EGT | CHT | Oil pressure | Oil temperature | Bus voltage | Alternator current |
|---|---|---|---|---|---|---|---|
| RMSE | 9 | 3.3 °C | 0.8 °C | 0.7 psi | 1.0 °C | 0.44 V | 0.8 A |
| p99 | 35 | 9.4 °C | 1.9 °C | 1.8 psi | 2.5 °C | 1.5 V | 2.9 A |

Use **residual = measured − expected** as features. Healthy residuals hover near zero in every profile; faults push them away. This one step makes the model work across all five profiles. The dataset includes the `expected_*` columns, and the live backend computes the same values, so the feature is available in production.

### 5.2 Window features

The backend gives your model the **last 60 samples (60 s)**. Compute per window:

- for each residual and each raw signal without a baseline (torque, fuel flow, injection timing/duration): **mean, std, slope** (least-squares over the window), **min, max**;
- **roughness** (§4.3) of the **RPM residual** (`rpm − expected_rpm`), `cht` and `torque`. Use the residual for RPM: raw RPM is legitimately jagged during fast throttle steps, which the baseline follows, so raw-RPM roughness gives false alarms in the rapid-throttle profile (the twin's own health scoring had exactly this bug, fixed while generating the dataset);
- **vibration RMS** (never the mean);
- the **fuel ratio** (§5.3);
- the window mean of the four flight conditions, as context.

Slopes matter for early detection: at 10–25 % strength a fault often shows as a steady drift before the level is clearly abnormal.

### 5.3 Commanded fuel (physics feature)

The ECU's injector pulse tells you how much fuel it asked for:

```
commanded_fuel_kgph = max(0, injection_duration_ms − 0.8) × 2.5 / 1000 × (rpm / 120) × 3.6
fuel_ratio          = fuel_flow / commanded_fuel_kgph        (ignore when rpm < 300)
```

(0.8 ms injector dead time, 2.5 g/s injector flow, 1 cylinder, 4-stroke. These are the same constants as `backend/twin/service.py`.)

### 5.4 Health scores

The dataset also has the backend's subsystem health scores (`health_thermal`, `health_combustion`, `health_lubrication`, `health_mechanical`, `health_electrical`, `health_injection`, `health_sensor`, 0–100). They're rule-based summaries computed live, so you may use them as features. But don't let the model become a copy of them: it should detect faults *earlier* than the rules (they're tuned to reach 30 at failure).

### 5.5 Never use as features

`sim_time`, `severity`, `failed`, `rul_seconds`, `fault_id`, run or mission IDs, the profile name or seed. These leak the answer or don't exist live.

---

## 6. Dataset

**The dataset is complete:** 299 runs (6 seeds × 5 profiles × 10 faults; one rapid-throttle vibration run, seed 4, was skipped because it crashed the simulator). It's shared as **`data/sim_v2_dataset.zip`** (17 MB; 57 MB unzipped). It's too large for git (ignored). Unzipped, it gives `sim_v2/runs.csv` and `sim_v2/runs/`. To regenerate or extend it (e.g. seeds 7–12), three steps:

```matlab
% 1. Simulate (MATLAB, from simulation/). Resumable: finished runs are skipped.
generate_sim_dataset('../data/sim_v2', 1:6)      % seeds 1-6 x 5 profiles x 10 faults = 300 runs
```
```bash
# 2. Add expected values, health, failure and labels (from the repo root)
python ai/dataset/label_dataset.py data/sim_v2
# 3. Sanity checks + failure summary
python ai/dataset/check_dataset.py data/sim_v2
```

Splits: seeds 1–4 train (199 runs), 5 val (50), 6 test (50).

### 6.1 Structure

- `data/sim_v2/runs.csv`: one row per run, with columns `run_id, profile, profile_seed, fault_id, onset_s, ramp_s, failure_s (empty if never), duration_s, split`.
- `data/sim_v2/runs/<run_id>.csv`: one row per second.

| Group | Columns |
|---|---|
| Time | `sim_time` (s since engine start; ground truth only) |
| Flight conditions | `throttle, engine_load, altitude, ambient_temperature` |
| Signals | the 12 in §2.2 |
| Expected healthy values | `expected_rpm, expected_egt, expected_cht, expected_oil_pressure, expected_oil_temperature, expected_battery_voltage, expected_alternator_current` |
| Health | `health_thermal … health_sensor` |
| Labels | `fault_id` (0 before onset, then the fault's ID), `severity` (0–1), `failed` (0/1), `rul_seconds` (capped at 600) |

### 6.2 Run timeline

```
0 s ──── warm-up (healthy) ──── onset (random 120–300 s) ──── ramp (per §4.1) ──── failure ── +60 s end
                                                                                  └─ or, if it never fails: hold 5 min, then end
```

Fault 0 runs are healthy throughout.

### 6.3 Splits

`runs.csv` assigns each run to `train`, `val` or `test` by seed: seeds 1–4 train, 5 val, 6 test. **Split by run, never by row.** Neighbouring seconds of one flight are nearly identical; mixing them across splits inflates every metric.

### 6.4 Class balance

Most rows are healthy: warm-up, pre-onset, fault 0 runs. Use class weights or balanced sampling for the classifier, and report per-class metrics, not plain accuracy.

---

### 6.5 What the rows look like

Real rows from two runs, both cruise variants (seed 1): one healthy, one overheating fault (onset 249 s, ramp 246 s, failure 403 s). Only some columns are shown.

| Row | sim_time | throttle | altitude | ambient_temperature | rpm | cht | expected_cht | egt | expected_egt | oil_temperature | health_thermal | fault_id | severity | failed | rul_seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Healthy run, mid-flight | 600 | 0.79 | 294 | 18.9 | 3502 | 60.0 | 59.9 | 553 | 554 | 91.1 | 98.0 | 0 | 0.00 | 0 | 600 |
| Healthy run, later | 900 | 0.79 | 294 | 18.9 | 3502 | 60.2 | 60.2 | 551 | 553 | 93.3 | 98.3 | 0 | 0.00 | 0 | 600 |
| Overheating run, before onset | 239 | 0.91 | 1078 | 8.6 | 3630 | 63.8 | 63.5 | 594 | 593 | 100.5 | 97.5 | 0 | 0.00 | 0 | 600 |
| Overheating, just after onset | 250 | 0.91 | 1078 | 8.6 | 3630 | 64.0 | 63.5 | 590 | 593 | 100.1 | 98.4 | 2 | 0.00 | 0 | 153 |
| Overheating, 25 % | 309 | 0.91 | 1078 | 8.6 | 3630 | 81.3 | 63.6 | 666 | 593 | 109.4 | 79.5 | 2 | 0.24 | 0 | 94 |
| Overheating, ~50 % | 373 | 0.91 | 1078 | 8.6 | 3630 | 119.0 | 63.6 | 740 | 593 | 120.5 | 7.7 | 2 | 0.50 | 0 | 30 |
| Overheating, failure | 403 | 0.91 | 1078 | 8.6 | 3630 | 137.5 | 63.6 | 778 | 593 | 127.1 | 0.0 | 2 | 0.63 | 1 | 0 |
| Overheating, after failure | 433 | 0.91 | 1078 | 8.6 | 3630 | 157.1 | 63.6 | 815 | 593 | 131.8 | 0.0 | 2 | 0.75 | 1 | 0 |

Things to notice:

- **Residuals tell the story:** in the healthy run `cht` ≈ `expected_cht`. In the overheating run, CHT climbs from 64 to 157 °C while `expected_cht` stays at 63.6, because the flight conditions didn't change.
- **The fault label switches at onset,** but the signals only drift visibly ~30–60 s later. That's the early-detection window.
- **`rul_seconds` stays 600 until onset** (the fault doesn't exist yet), then counts down to failure.
- **`health_thermal` falls through 30 shortly before `failed` turns 1,** because failure uses the 90 s average.

## 7. Algorithms (recommended)

### 7.1 Part A — anomaly detector

| Option | What | Why / when |
|---|---|---|
| **A1. Residual Mahalanobis (baseline, build first)** | Fit mean and covariance of the healthy window-feature vectors; score = Mahalanobis distance | Ten lines of numpy, explainable, strong because residuals are already condition-independent. Your yardstick |
| **A2. Dense autoencoder on window features (recommended main)** | Encoder 64→32→8, mirrored decoder, trained **only on healthy windows**; score = reconstruction error | Learns correlations between features (e.g. EGT vs fuel). Small enough for edge/onboard use (a PS innovation point) |
| A3. LSTM / 1D-CNN autoencoder on the raw 60 × N sequence | Same idea on sequences | Only if A2 misses roughness-type faults; slower and heavier |

**Training data:** healthy windows only. That's fault 0 runs, plus every run's samples before onset, excluding the first 60 s of warm-up.

**Threshold:** the 99.5th percentile of the score on healthy **validation** windows. Then add **persistence**: alarm only when, say, 5 of the last 10 windows exceed it. This suppresses one-off spikes during rapid throttle without delaying real faults much.

**Don't** use Isolation Forest or one-class SVM as the main model. They work, but they're harder to threshold and explain than A1/A2, and give no benefit here.

### 7.2 Part B — fault classifier

| Option | What | Why / when |
|---|---|---|
| **B1. XGBoost / LightGBM on window features (recommended)** | 10-class softmax on §5 features, class weights | Fast to train, strong on tabular features, and explainable: **SHAP values show which signals drove each diagnosis**, the PS's "explainable AI for fault diagnosis" |
| B2. 1D-CNN or GRU on the raw 60 × N window | Learns its own features | Only if B1 confuses pairs from §4.5 after you've added the features listed there |

**Labels:** `fault_id` of the window's last sample.

**Early samples:** drop windows where 0 < severity < 0.05 from **training**. They're physically indistinguishable from healthy and only teach noise. Keep them in **evaluation**.

**Post-processing:** smooth the predicted class over the last ~10 s (majority or averaged probabilities) so the dashboard doesn't flicker.

**Optional bonus:** add a second output, "fault will reach failure within 5 min" (yes/no, from `rul_seconds < 300`). It turns the classifier into an explicit early-warning model, and it's a nice bridge to the RUL model.

### 7.3 How A and B work together live

```
every second:
  anomaly_score = A(window)
  fault, confidence = B(window)
  if anomaly persists or (fault != 0 and confidence high for ~10 s):
      alert "<fault name> developing"            ← early warning
```

---

## 8. Evaluation (what to report)

Evaluate on the **test** runs. Report everything **per mission profile** as well as overall.

| Metric | Definition | Target to aim for |
|---|---|---|
| **Lead time before failure** | failure time − time the fault was first correctly identified *and stayed* identified (≥ 10 s) | As large as possible; ≥ 60 % of the onset-to-failure window |
| **Detection delay** | Seconds after onset until detected | Report per fault |
| **Severity at detection** | Fault strength at that moment | ≤ 0.25 for most faults |
| **False alarm rate** | Anomaly or fault alarms per hour on healthy test runs (fault 0 + pre-onset) | < 1 per hour, especially in rapid throttle |
| **Per-class precision / recall / F1** | On windows with severity ≥ 0.25 | ≥ 0.9 |
| **Confusion matrix** | 10 × 10 | Check the §4.5 pairs |
| **Missed faults** | Runs where the fault is never correctly identified | 0 |

Include one plot per fault showing anomaly score and class probability over time, with onset and failure marked. That's the picture that convinces judges you "predict before it occurs".

---

## 9. Pitfalls

- **Raw-value thresholds don't transfer between profiles.** Use residuals.
- **Vibration mean is noise.** Use RMS.
- **Torque is very noisy.** Use window means and roughness, not single samples.
- **The first minute is warm-up.** Don't train the anomaly detector on t < 60 s, and don't count alarms there.
- **Fault 7 is a sensor fault.** CHT looks hot, but the engine is fine. The classifier should call it 7, not overheating. EGT and oil temperature tell them apart.
- **Low-power runs have weaker faults** (§4.4). Make sure the test set covers endurance and high altitude.
- **Electrical sag at low RPM is healthy** in rapid throttle (bus down to ~25.3 V). The baseline expects it, so trust the residual.
- **Leakage:** never feed time, severity, labels or run identifiers (§5.5), and never split by row.
- **Simulator randomness:** the Simulink noise and misfire generators have fixed seeds, so the live demo always replays the same noise. The dataset generator gives each of the model's 16 noise sources its own random seed in every run, so no two runs share a noise pattern. The splits keep each seed in one split only.
- **Fixed during generation:** eight sensor-noise sources (RPM, fuel flow, torque, oil temperature, oil pressure, CHT, EGT and the vibration source) used to share one seed. Their noise was therefore perfectly correlated, which a model could have learned as a fake relationship. They now have separate seeds, in the model and in every dataset run.
- **CHT can read 0 °C** (the sensor's lower limit) when a lean injector fault meets very cold air at high altitude (2 runs). Treat it like any clipped reading.
- **Oil temperature can saturate at 200 °C** (the sensor's range limit) in severe oil pressure failure, mostly on hot or high-power flights. Treat 200 as "200 or more". The oil pressure signal still shows the fault clearly.

---

## 10. Handing the model back

The interface your model plugs into is already in place: `backend/twin/predictor.py`. Today the live system runs a rule-based stand-in (`RuleFaultModel`) through the same interface, so the dashboard, advisory and mission reports already work. Integrating your model means implementing one class and returning it from `create_predictors()`.

Once per second, the backend calls `predict(window)` with the **last 60 samples** (oldest first). Each sample is a dict with the column names of §6.1 (flight conditions, signals, `expected_*`, `health_*`), minus the labels.

**Deliver:**

1. A class with `predict(window: list[dict]) -> FaultResult` (see `predictor.py`), returning
   ```python
   FaultResult(
       anomaly_score=...,   # normalised: 1.0 = your detection threshold (divide by it)
       is_anomaly=...,      # anomaly_score >= 1.0, after your persistence rule
       fault_id=...,        # 0 healthy, 1-9 faults (predictor.FAULTS)
       fault_family=...,    # predictor.FAULTS[fault_id][0]
       fault=...,           # predictor.FAULTS[fault_id][1]
       confidence=...,      # 0-1, probability of fault_id
       top_features=[("oil_pressure", 0.42), ...],   # optional, e.g. from SHAP
       source="xgboost-v1", # your model's name, shown on the dashboard
   )
   ```
2. **Model files:**
   - XGBoost / LightGBM: `save_model("*.json")`
   - PyTorch: `state_dict` `.pt`
   - Keras: `.keras`
3. **Feature scaling** as **JSON** (means / stds), not sklearn pickles. The backend runs scikit-learn 1.6.1, and pickles break between versions.
4. **The threshold and persistence settings** as JSON.
5. **A short results note** with the §8 metrics.

**Constraints:**
- **Speed:** under 50 ms per call on a laptop CPU.
- **Size:** ideally under 10 MB. Lightweight models suit onboard / edge deployment, which the PS lists as an innovation area.

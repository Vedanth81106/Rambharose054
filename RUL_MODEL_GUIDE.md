# Remaining Useful Life (RUL) Model — Training Guide

This guide is for whoever trains the RUL model of the aero-piston engine digital twin. It covers what the model must predict, how failure is defined, how the labels are built, which algorithms to use, how to evaluate, and how to hand the model back so the live system can run it.

It shares the simulator, mission profiles, faults and dataset with the anomaly model. **Read [`ANOMALY_MODEL_GUIDE.md`](ANOMALY_MODEL_GUIDE.md) sections 2–6 first.** They describe the engine, the 12 signals and 4 flight conditions, what a healthy engine reads in each mission profile, what every fault does to the signals, and the features (residuals, roughness, fuel ratio). This guide only repeats what matters specifically for RUL.

All numbers were measured from the Simulink model the dataset was generated with (commit `c6764ed`, October 2026). They are simulator values, not certified engine limits.

---

## 1. What the model has to do

The problem statement asks for **estimating degradation trends and remaining useful life**, **predicting probable failures before occurrence**, and **predictive maintenance recommendations**. The RUL model answers:

> **"If this keeps going, how many seconds until the engine fails?"**

The anomaly model says *what* is wrong; the RUL model says *how urgent* it is. Together they drive the maintenance advisory, e.g. "Oil pressure failure developing — about 90 s to failure — land or reduce power".

The model has to:

- predict **"far from failure"** for a healthy engine, in every mission profile, without false countdowns;
- start a **countdown** once a fault begins degrading the engine;
- infer **how fast** the fault is progressing from the signal trend. The same fault can take 8 or 15 minutes to develop, and the model can't know which in advance;
- become **more accurate as failure approaches**, which is where it matters most.

---

## 2. What "failure" means

Failure is defined once, in `backend/twin/failure.py`, and used both for the training labels and by the live dashboard:

> The engine has failed when the health of its **weakest engine subsystem** (thermal, combustion, lubrication, mechanical, electrical or injection), **averaged over the last 90 s**, drops below **30 / 100** and stays below until the end of the run.

- **Health scores** (0–100) come from `DigitalTwinService.calculate_health()` in `backend/twin/service.py`. They compare each signal with what a healthy engine should read in the same flight conditions, so a high-altitude or hot-day flight doesn't count as degradation.
- **Sensor health is excluded.** A failing CHT sensor (fault 7) makes a reading untrustworthy but doesn't shorten engine life, so it never starts a countdown.
- **Healthy engines never fail.** All 40 healthy test flights across every profile stayed at health ≥ 80.

---

## 3. How faults progress toward failure

Every fault starts with zero effect at its onset and grows linearly to full strength over its ramp time. Where along that ramp the engine fails depends on the fault and on how hard the engine is working. The table shows:

- **Fails at:** fault strength at failure, from reference runs at cruise and in endurance with a 5-minute ramp.
- **Onset → failure:** measured in the full dataset (299 runs, 6 per fault and profile), with its random ramp times.

| Fault | Fails at (cruise / endurance) | Ramp in dataset | Onset → failure in the dataset (runs failing) |
|---|---|---|---|
| 1 Misfire | 33 % / 39 % | 3–6 min | 85–177 s, median 101 (30/30) |
| 2 Overheating | 56 % / 70 % | 3–6 min | 141–241 s, median 176 (30/30) |
| 3 Oil pressure failure | 61 % / 73 % | 1–3 min | 94–140 s, median 110 (30/30) |
| 4 Fuel starvation | 86 % / after full strength | 1–3 min | 106–206 s, median 147 (30/30) |
| 5 Injector abnormality | 88 % / after full strength | 8–15 min | 430–1137 s, median 581 (25/30; 5 low-power runs never fail) |
| 6 Cooling degradation | after full strength (CHT keeps creeping up) | 8–15 min | 501–949 s, median 694 (30/30) |
| 7 CHT sensor drift | never (sensor fault) | 8–15 min | no failure (0/30) |
| 8 Combustion instability | 55 % / 99 % | 8–15 min | 292–1082 s, median 531 (29/30) |
| 9 Abnormal vibration | after full strength | 8–15 min | 425–1063 s, median 650 (29/29) |

With short ramps, oil pressure failure and fuel starvation usually fail right at the end of the ramp: the 90 s health average lags a fast collapse. The dataset's `failure_s` column is the truth for every run.

**Low power slows faults down.** In the endurance profile, faults reach failure 20–70 % later than at cruise, and several only after reaching full strength: less heat to shed, less vibration at lower RPM. A few low-power runs never reach failure at all (5 injector runs in endurance and high altitude, 1 combustion-instability run in rapid throttle); their `failure_s` is empty and `rul_seconds` stays 600. So the model must learn that the *same* fault is more or less urgent depending on how the engine is being flown.

**The time scale is compressed:** real engines degrade over hours, here over minutes. Treat seconds as "simulator seconds" and say so in the demo.

---

## 4. Labels

Each row of the dataset (`data/sim_v2/runs/<run_id>.csv`, see the anomaly guide §6) has:

| Column | Meaning |
|---|---|
| `rul_seconds` | **Training target.** 600 before the fault's onset; from onset `min(600, failure_s − sim_time)`; 0 at and after failure |
| `failed` | 1 from the failure moment on |
| `severity` | Fault strength 0–1 (ground truth; evaluation only) |
| `fault_id` | 0 before onset, then the fault's ID |

`runs.csv` also gives `onset_s`, `ramp_s` and `failure_s` per run. `failure_s` is empty if the run never fails.

### 4.1 Why the label is capped at 600 s

Far from failure, the exact number of seconds is unknowable and doesn't matter. "Fails in 40 minutes" and "fails in 60 minutes" call for the same action. The cap:

- makes healthy flights and faults that never fail well-defined: **600 throughout**, meaning "10 minutes or more";
- concentrates the model on the last 10 minutes, where the countdown matters;
- is the standard approach in engine-RUL research (e.g. NASA's C-MAPSS turbofan dataset uses a capped, piecewise-linear target).

The resulting label looks like this:

```
Slow fault (onset → failure longer than 600 s):

rul_seconds
 600 ───────────────────────────────────╮
                                        │╲        (falls 1 s per second)
                                        │  ╲
   0                                    │    ╲____ (0 after failure)
     engine start      onset      failure − 600 s   failure

Fast fault (onset → failure shorter than 600 s):

 600 ──────────────╮
                   │
                   ╰╲                    (drops at onset to the true time left,
                     ╲                    then falls 1 s per second)
   0                   ╲____
     engine start    onset   failure
```

**Before onset the label is always 600,** even if failure comes within 10 minutes of that moment. The fault doesn't exist yet, so no signal can reveal it. Counting down there would teach the model noise. The drop at onset for fast faults is the honest "fault just appeared" moment. The model can't see it instantly, so expect the largest errors in the first 30–60 s after onset, and report them (§7).

### 4.2 Rows to drop or weight

- **First 60 s of every run (warm-up):** the backend doesn't score health before 60 samples. Drop them.
- **Rows after failure:** keep up to 60 s (label 0) so the model learns "failed now", then the run ends.
- **Imbalance:** most rows are 600 (healthy, pre-onset, never-failing). Down-sample them or give rows with `rul_seconds < 600` higher loss weight. Otherwise the model learns to always say 600.

---

## 5. Inputs

Use the same building blocks as the anomaly model (anomaly guide §5), but over a **longer history**: RUL depends on the *trend*, not just the current state.

| Input | Why it matters for RUL |
|---|---|
| **Residuals** (signal − `expected_*`) for RPM, EGT, CHT, oil pressure, oil temperature, bus voltage, alternator current | How far the engine has drifted from healthy |
| **Health scores** `health_thermal … health_injection` | Failure is defined on these, so their trend is the most direct RUL signal |
| **Weakest engine health**, raw and 90 s-averaged (sensor excluded) | Exactly the quantity the failure definition thresholds |
| Roughness of RPM, CHT, torque; vibration RMS; fuel ratio | Needed for misfire, instability, vibration and injector faults, whose health is driven by these |
| Torque, fuel flow, injection timing/duration (raw) | Signals without a baseline |
| Flight conditions (throttle, load, altitude, ambient) | The same fault is more or less urgent at different power (§3) |

**Sequence length:** 180–300 s at 1 Hz. The live backend can provide up to 1200 samples per call. Shorter windows can't see the trend of slow faults; longer ones add little.

**Never use as input:** `sim_time`, `severity`, `failed`, `fault_id`, `rul_seconds`, `onset_s`, `ramp_s`, `failure_s`, run/mission IDs, profile name or seed. These leak the answer or don't exist live.

**Optional — fault probabilities from the anomaly classifier:** knowing *which* fault is developing helps, because faults progress differently. If you use them, train on **out-of-fold** classifier predictions (generated by a classifier that never saw that run). Otherwise the RUL model learns from unrealistically perfect labels.

---

## 6. Algorithms

### 6.1 Build the baseline first: health extrapolation

Before any ML, implement this (about 20 lines):

1. Take the weakest engine health, averaged over 90 s, for the last ~120 s.
2. Fit a straight line. If it's falling, extrapolate to where it would cross 30. That time is the RUL estimate.
3. If it's flat or rising: RUL = 600.

It's physics-transparent and uses exactly the failure definition, so it's a fair benchmark. **Your ML model must beat it**, especially early in a fault, where health is still near 100 and its slope says little.

### 6.2 Main model: GRU (recommended)

| | Recommendation |
|---|---|
| Architecture | 2-layer GRU, 64–96 hidden units, dropout 0.15–0.2 → dense layer → one output. The class in `rul-model-new/rul/model.py` (`GRURULRegressor`: GRU → LayerNorm → 64-unit GELU layer → output) has this shape and trained the live model |
| Input | Sequence of 180–300 × N features (§5), standardised with training-set means and stds |
| Target | `rul_seconds / 600` (0–1); output through a sigmoid, then × 600 |
| Loss | Huber, with extra weight on rows where `rul_seconds < 600` |
| Training samples | Sliding windows, stride 5–10 s, from **train** runs; split by run (seeds 1–4 train, 5 val, 6 test) |
| Training | Adam, lr 1e-3, early stopping on validation RMSE (in-horizon rows) |

**Why a GRU:** RUL is about how the state *evolves*. Recurrent models read trends naturally, and a GRU is lighter than an LSTM, which suits onboard / edge use (an innovation point in the PS).

### 6.3 Alternatives

| Option | When to use |
|---|---|
| **XGBoost / LightGBM** on window features (means, slopes and roughness over several horizons, e.g. last 30/90/300 s) | Quick strong baseline. Often competitive, and explainable with SHAP |
| **1D-CNN or temporal convolution** | If the GRU is slow to train or unstable |
| **Quantile outputs** (predict the 10th, 50th and 90th percentile of RUL with pinball loss) | Recommended extra: gives a confidence band ("failure in 90 s, likely 60–130 s"). Very useful for the maintenance advisory and for judges |

### 6.4 Post-processing

- **Clamp:** keep the output in 0–600.
- **Smooth:** an exponential average over ~5 s stops the countdown jittering.
- **Monotonic countdown (display only):** once a fault is confirmed, the displayed RUL shouldn't jump up by more than a small margin. Keep raw predictions for evaluation.

---

## 7. Evaluation (what to report)

Evaluate on the **test** runs. Report everything **overall, per fault and per mission profile**.

| Metric | Definition | Target to aim for |
|---|---|---|
| **RMSE, in-horizon** | RMSE on rows with true RUL < 600 | Lower than the §6.1 baseline everywhere |
| **RMSE, last 120 s** | Rows within 2 minutes of failure | Small: this is when decisions are made |
| **Accuracy along the fault** | Error at 25 %, 50 % and 75 % of each run's onset → failure interval | Error shrinks as failure approaches |
| **Warning timeliness** | Time of the first prediction below 300 s vs the true moment RUL reached 300 s | Within ±30 s; late is worse than early |
| **Asymmetric score** | Σ over rows of `exp(−d/13) − 1` if d < 0 (early) and `exp(d/10) − 1` if d > 0 (late), with d = (predicted − true) / 10 s | Lower is better; punishes predicting failure *later* than reality |
| **False countdowns** | Share of healthy and never-failing rows predicted below 400 s | ≈ 0 |
| **Never-failing runs** | Fault 7 (sensor drift) everywhere, plus any engine-fault run whose `failure_s` is empty: predictions should stay near 600 | Report separately |

The asymmetric score comes from the NASA PHM'08 prognostics challenge. Overestimating remaining life is dangerous; underestimating only costs an early landing.

**Plots to include:** predicted vs true RUL over time for one run per fault, with the quantile band if you have one, and onset and failure marked. This is the picture that shows judges the system predicts failure before it happens.

---

## 8. Pitfalls

- **Raw values across profiles:** a healthy high-altitude flight looks "degraded" in raw terms. Use residuals and health scores.
- **Always predicting 600:** the imbalance makes this the easy minimum. Weight in-horizon rows (§4.2) and watch in-horizon RMSE, not overall RMSE.
- **Learning the clock:** never input `sim_time`. The dataset randomises onset (120–300 s) and ramp time so the model can't learn "failure happens N seconds after start".
- **Learning the ramp:** ramp times are random within each fault's range, so the model must read the *rate* of degradation from the signals. Don't add features that encode the ramp.
- **Sensor fault 7:** CHT looks alarming, but the label is 600 throughout. The model must learn to ignore a sensor that disagrees with EGT, oil temperature and the rest.
- **Warm-up:** the first 60 s are dropped; health is not defined there.
- **Split by run, never by row:** neighbouring windows overlap almost completely.
- **Fixed during generation:** the first version of the labelling script started the countdown up to 10 minutes *before* the fault began. That's impossible to predict, and is now fixed (600 until onset, §4.1). Separately, eight sensor-noise sources in the Simulink model shared one seed, giving perfectly correlated noise. They now have separate seeds, and every dataset run uses its own random seeds.
- **The old RUL pipeline (since removed)** was trained on an older dataset, with labels from a synthetic damage-accumulation health index (failure at HI ≤ 0.1, output in hours). Don't mix those labels with the new ones. The new label is `rul_seconds` from the shared failure definition.

---

## 9. Handing the model back

The interface your model plugs into is already in place: `backend/twin/predictor.py`. Today the live system runs the §6.1 health-extrapolation baseline (`HealthTrendRULModel`) through the same interface, so the dashboard countdown, advisory and mission reports already work. Integrating your model means implementing one class and returning it from `create_predictors()`.

Once per second, the backend calls `predict(history)` with the **last 300 samples** of the current mission (oldest first; tell us if you need more, up to 1200). Each sample is a dict with the column names of the anomaly guide §6.1, minus the labels.

**Deliver:**

1. A class with `predict(history: list[dict]) -> RULResult | None` (see `predictor.py`), returning
   ```python
   RULResult(
       rul_seconds=...,     # 0-600; 600 = "10 min or more"
       rul_low=..., rul_high=...,   # optional band (e.g. 10th / 90th percentile)
       source="gru-v1",     # your model's name, shown on the dashboard
   )
   ```
   Return `None` if there are fewer samples than the model needs.
2. **Weights** as a PyTorch `state_dict` (`.pt`), plus the model class (or reuse `GRURULRegressor`), or XGBoost `save_model("*.json")`.
3. **Input scaling** as **JSON** (means / stds per feature), not an sklearn pickle. The backend runs scikit-learn 1.6.1, and pickles break between versions.
4. **The feature list and sequence length** as JSON, so the backend builds inputs in the same order.
5. **A short results note** with the §7 metrics and plots, including the comparison with the §6.1 baseline.

**Constraints:**
- **Speed:** under 50 ms per call on a laptop CPU.
- **Size:** ideally under 10 MB.

The backend, API and dashboard already use seconds (`rul_seconds`, shown as "~2 min 30 s").

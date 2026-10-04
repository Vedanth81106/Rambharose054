"""RUL model input features, shared by data preparation and the live backend.

One function turns a run's (or a live mission's) 1 Hz history into the
feature table, so training and inference compute exactly the same thing.

Copy of rul-model-new/rul/rul_features.py, which trained the model in
ml_models/rul_gru/. Keep the two identical; retrain after changing either.
"""

import numpy as np
import pandas as pd


SEQ_LEN = 180                 # seconds of history per sample
WARMUP = 60                   # the twin scores nothing before this
ROLL = 30                     # roughness / vibration RMS window
HEALTH_AVG = 90               # failure definition averages health over 90 s

# History needed for a full-quality sample: the sequence plus the longest
# rolling window feeding its first row.
HISTORY_NEEDED = SEQ_LEN + HEALTH_AVG - 1


FEATURE_COLUMNS = [
    # Operating conditions and raw telemetry
    "throttle",
    "engine_load",
    "altitude",
    "ambient_temperature",
    "rpm",
    "torque",
    "fuel_flow",
    "cht",
    "egt",
    "oil_pressure",
    "oil_temperature",
    "vibration",
    "battery_voltage",
    "alternator_current",
    "injection_timing",
    "injection_duration",

    # Residuals against the healthy baseline
    "rpm_residual",
    "egt_residual",
    "cht_residual",
    "oil_pressure_residual",
    "oil_temperature_residual",
    "battery_voltage_residual",
    "alternator_current_residual",

    # Engine health
    "health_thermal",
    "health_combustion",
    "health_lubrication",
    "health_mechanical",
    "health_electrical",
    "health_injection",

    # Weakest health (the failure definition thresholds its 90 s average)
    "weakest_health",
    "weakest_health_90s",

    # Degradation features
    "rpm_roughness",
    "cht_roughness",
    "torque_roughness",
    "vibration_rms",
]

RESIDUAL_MAP = {
    "rpm": "expected_rpm",
    "egt": "expected_egt",
    "cht": "expected_cht",
    "oil_pressure": "expected_oil_pressure",
    "oil_temperature": "expected_oil_temperature",
    "battery_voltage": "expected_battery_voltage",
    "alternator_current": "expected_alternator_current",
}

HEALTH_ENGINE_COLS = [
    "health_thermal",
    "health_combustion",
    "health_lubrication",
    "health_mechanical",
    "health_electrical",
    "health_injection",
]


def roughness(x):
    """Median |x[i] - (x[i-1] + x[i+1]) / 2| (ANOMALY_MODEL_GUIDE.md §4.3)."""
    if len(x) < 3:
        return 0.0
    return float(np.median(np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2)))


def build_features(df):
    """Feature table (one row per sample) from a 1 Hz history, oldest first.

    `df` needs the dataset columns: signals, flight conditions, expected_*
    and health_*. Rows are not dropped, so the result lines up with `df`.
    """

    d = pd.DataFrame(index=df.index)

    for col in FEATURE_COLUMNS[:16]:
        d[col] = df[col]

    for actual, expected in RESIDUAL_MAP.items():
        d[f"{actual}_residual"] = df[actual] - df[expected]

    # Health is missing for a few samples; carry the last value.
    health = df[HEALTH_ENGINE_COLS].ffill().bfill().fillna(100.0)
    for col in HEALTH_ENGINE_COLS:
        d[col] = health[col]

    d["weakest_health"] = health.min(axis=1)
    d["weakest_health_90s"] = (
        d["weakest_health"].rolling(HEALTH_AVG, min_periods=1).mean()
    )

    # Roughness of the RPM residual, not raw RPM: raw RPM is legitimately
    # jagged during rapid-throttle steps, which the baseline follows.
    d["rpm_roughness"] = (
        d["rpm_residual"].rolling(ROLL, min_periods=3).apply(roughness, raw=True)
    )
    d["cht_roughness"] = (
        df["cht"].rolling(ROLL, min_periods=3).apply(roughness, raw=True)
    )
    d["torque_roughness"] = (
        df["torque"].rolling(ROLL, min_periods=3).apply(roughness, raw=True)
    )
    d["vibration_rms"] = np.sqrt(
        (df["vibration"] ** 2).rolling(ROLL, min_periods=1).mean()
    )

    return d[FEATURE_COLUMNS].fillna(0.0)


def sequence_ending_at(features, end):
    """SEQ_LEN rows ending at row `end` (inclusive), left-padded with the
    first row when less history exists, so samples are available from the
    end of warm-up instead of only after SEQ_LEN seconds."""

    start = end - SEQ_LEN + 1
    if start >= 0:
        return features[start:end + 1]
    pad = np.repeat(features[:1], -start, axis=0)
    return np.concatenate([pad, features[:end + 1]], axis=0)

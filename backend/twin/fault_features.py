"""Input features of the trained fault models (XGBoost classifier, autoencoder).

The models in ml_models/fault/ were delivered without their feature code, so
these definitions are reconstructed from the feature names and
ANOMALY_MODEL_GUIDE.md §5. On the test split they reproduce the expected
accuracy (classifier F1 >= 0.93 on 8 of 9 faults), and varying the
ambiguous window lengths changes almost nothing. Replace them with the
training code when it arrives.

Needs LOOKBACK samples (the *_diff_60s features compare with 60 s ago).
"""

import numpy as np
import pandas as pd


LOOKBACK = 61

FEATURE_COLUMNS = [
    "rpm_res", "egt_res", "cht_res", "oil_press_res", "oil_temp_res", "battery_res",
    "fuel_ratio", "rpm_res_smooth", "cht_diff_10s",
    "rpm_res_diff_60s", "egt_res_diff_60s", "oil_press_res_diff_60s",
    "vibration_diff_60s", "throttle_diff_60s",
    "rpm_res_mean_60s", "egt_res_mean_60s", "oil_press_res_mean_60s",
    "vibration_rms", "rpm_roughness", "cht_roughness", "torque_roughness",
    "throttle", "injection_duration",
]

def _roughness(x):
    if len(x) < 3:
        return 0.0
    return float(np.median(np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2)))


def build_fault_features(df):
    """One feature row per sample of a 1 Hz history (oldest first).

    Early rows lack the 60 s lookback; their diff features are NaN, which
    XGBoost treats as missing. Callers use the last row.
    """

    f = pd.DataFrame(index=df.index)
    f["rpm_res"] = df["rpm"] - df["expected_rpm"]
    f["egt_res"] = df["egt"] - df["expected_egt"]
    f["cht_res"] = df["cht"] - df["expected_cht"]
    f["oil_press_res"] = df["oil_pressure"] - df["expected_oil_pressure"]
    f["oil_temp_res"] = df["oil_temperature"] - df["expected_oil_temperature"]
    f["battery_res"] = df["battery_voltage"] - df["expected_battery_voltage"]

    # Not the guide's measured / commanded fuel: the training notebook used
    # fuel flow per ms of injector pulse (its scaler: healthy mean 0.22,
    # std 0.039; this gives 0.21 / 0.038 on the healthy training runs).
    f["fuel_ratio"] = df["fuel_flow"] / df["injection_duration"].replace(0, np.nan)

    f["rpm_res_smooth"] = f["rpm_res"].rolling(10, min_periods=1).mean()
    f["cht_diff_10s"] = df["cht"].diff(10)
    for name, series in (
        ("rpm_res", f["rpm_res"]),
        ("egt_res", f["egt_res"]),
        ("oil_press_res", f["oil_press_res"]),
        ("vibration", df["vibration"]),
        ("throttle", df["throttle"]),
    ):
        f[f"{name}_diff_60s"] = series.diff(60)
    for name in ("rpm_res", "egt_res", "oil_press_res"):
        f[f"{name}_mean_60s"] = f[name].rolling(60, min_periods=1).mean()

    f["vibration_rms"] = np.sqrt((df["vibration"] ** 2).rolling(60, min_periods=1).mean())
    f["rpm_roughness"] = f["rpm_res"].rolling(60, min_periods=3).apply(_roughness, raw=True)
    f["cht_roughness"] = df["cht"].rolling(60, min_periods=3).apply(_roughness, raw=True)
    f["torque_roughness"] = df["torque"].rolling(60, min_periods=3).apply(_roughness, raw=True)
    f["throttle"] = df["throttle"]
    f["injection_duration"] = df["injection_duration"]
    return f[FEATURE_COLUMNS]

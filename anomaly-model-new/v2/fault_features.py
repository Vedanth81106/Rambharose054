"""Input features of the fault classifier and the anomaly autoencoder.

Shared by training (this folder) and the live backend (copied to
backend/twin/fault_features.py), so both compute exactly the same thing.
Change features only here, then retrain both models.

One function turns a 1 Hz history (a dataset run or a live mission, oldest
first) into one feature row per sample. Rows need LOOKBACK samples of
history for every feature to be defined.
"""

import numpy as np
import pandas as pd


LOOKBACK = 61                 # *_diff_60s compares with 60 s ago

FEATURE_COLUMNS = [
    # Residuals: measured - expected healthy value (ANOMALY_MODEL_GUIDE.md §5.1)
    "rpm_res", "egt_res", "cht_res", "oil_press_res", "oil_temp_res", "battery_res",
    # Measured / commanded fuel (guide §5.3): healthy ~1.0, injector fault ~0.7
    "fuel_ratio",
    "rpm_res_smooth", "cht_diff_10s",
    # Change over the last 60 s: value now minus value 60 s ago
    "rpm_res_diff_60s", "egt_res_diff_60s", "oil_press_res_diff_60s",
    "vibration_diff_60s", "throttle_diff_60s",
    # 60 s window means
    "rpm_res_mean_60s", "egt_res_mean_60s", "oil_press_res_mean_60s",
    # Roughness and vibration (guide §4.3), 60 s windows
    "vibration_rms", "rpm_roughness", "cht_roughness", "torque_roughness",
    # Operating point
    "throttle", "injection_duration",
    # Window statistics that separate misfire (one-sided RPM dips, mean RPM
    # falls) from combustion instability (symmetric scatter)
    "rpm_res_median_60s", "rpm_res_p10_60s", "rpm_res_p90_60s",
    "rpm_res_std_60s", "rpm_res_skew_60s", "rpm_dip_frac_60s",
    "egt_res_median_60s", "torque_mean_60s", "vibration_rms_30s",
]

# Injector constants (backend/twin/service.py, guide §5.3)
INJECTOR_DEAD_TIME_MS = 0.8
INJECTOR_FLOW_GPS = 2.5
RPM_DIP = 100.0               # an RPM dip: this far below the window median


def _roughness(x):
    """Median |x[i] - (x[i-1] + x[i+1]) / 2| (guide §4.3)."""
    if len(x) < 3:
        return 0.0
    return float(np.median(np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2)))


def build_fault_features(df):
    """One feature row per sample. `df` has the dataset columns: signals,
    flight conditions and expected_*. Early rows lack the lookback; their
    window features are NaN (XGBoost treats NaN as missing)."""

    f = pd.DataFrame(index=df.index)
    f["rpm_res"] = df["rpm"] - df["expected_rpm"]
    f["egt_res"] = df["egt"] - df["expected_egt"]
    f["cht_res"] = df["cht"] - df["expected_cht"]
    f["oil_press_res"] = df["oil_pressure"] - df["expected_oil_pressure"]
    f["oil_temp_res"] = df["oil_temperature"] - df["expected_oil_temperature"]
    f["battery_res"] = df["battery_voltage"] - df["expected_battery_voltage"]

    commanded = (
        np.maximum(0.0, df["injection_duration"] - INJECTOR_DEAD_TIME_MS)
        * INJECTOR_FLOW_GPS / 1000 * (df["rpm"] / 120) * 3.6
    )
    ratio = df["fuel_flow"] / commanded.replace(0, np.nan)
    f["fuel_ratio"] = ratio.where(df["rpm"] >= 300, 1.0).fillna(1.0)

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

    window = f["rpm_res"].rolling(60, min_periods=10)
    median = window.median()
    f["rpm_res_median_60s"] = median
    f["rpm_res_p10_60s"] = window.quantile(0.10)
    f["rpm_res_p90_60s"] = window.quantile(0.90)
    f["rpm_res_std_60s"] = window.std()
    f["rpm_res_skew_60s"] = window.skew()
    f["rpm_dip_frac_60s"] = (
        (f["rpm_res"] < median - RPM_DIP).astype(float).rolling(60, min_periods=10).mean()
    )
    f["egt_res_median_60s"] = f["egt_res"].rolling(60, min_periods=10).median()
    f["torque_mean_60s"] = df["torque"].rolling(60, min_periods=10).mean()
    f["vibration_rms_30s"] = np.sqrt((df["vibration"] ** 2).rolling(30, min_periods=1).mean())

    return f[FEATURE_COLUMNS]

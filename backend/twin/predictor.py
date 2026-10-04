"""Fault and RUL predictors: the interface the trained models plug into.

The digital twin calls two predictors once per telemetry sample:

* a FaultModel gets up to RUL_HISTORY_SAMPLES samples (the stand-in uses
  the latest WINDOW_SAMPLES) and says whether the engine is anomalous and
  which fault is developing;
* a RULModel gets up to RUL_HISTORY_SAMPLES samples and estimates the
  seconds until failure (backend/twin/failure.py), capped at RUL_CAP_S.

Each sample is a dict with the dataset column names (ANOMALY_MODEL_GUIDE.md
§6.1): flight conditions, the 12 signals, expected_* healthy values and
health_* scores, oldest first.

Until the trained models are delivered, rule-based stand-ins fill both
roles, so the whole system works end to end: RuleFaultModel (residual- and
roughness-based diagnosis) and HealthTrendRULModel (the RUL guide's §6.1
baseline). A trained model replaces a stand-in by implementing the same
predict() method; see create_predictors().
"""

import json
import logging
from math import log2, sqrt
from pathlib import Path
from statistics import median
from typing import Protocol

from pydantic import BaseModel

from twin.failure import (
    FAILURE_THRESHOLD,
    SMOOTHING_WINDOW,
    SUBSYSTEMS,
)


logger = logging.getLogger(__name__)

WINDOW_SAMPLES = 60
RUL_HISTORY_SAMPLES = 300
RUL_CAP_S = 600.0

# Fault_ID -> (fault family used by the advisory rules, display name).
FAULTS = {
    0: ("healthy", "Healthy"),
    1: ("misfire", "Misfire"),
    2: ("overheating", "Overheating"),
    3: ("oil_pressure", "Oil pressure failure"),
    4: ("fuel_starvation", "Fuel starvation"),
    5: ("injector", "Injector abnormality"),
    6: ("cooling", "Cooling degradation"),
    7: ("cht_sensor", "CHT sensor drift"),
    8: ("instability", "Combustion instability"),
    9: ("vibration", "Abnormal vibration"),
}
FAMILY_TO_ID = {family: fault_id for fault_id, (family, _) in FAULTS.items()}

# Families the rules can name that are not one of the simulated faults.
EXTRA_FAMILIES = {
    "electrical": "Electrical system fault",
    "unclassified": "Unclassified anomaly",
}


class FaultResult(BaseModel):
    # Normalised so that 1.0 is the model's detection threshold.
    anomaly_score: float
    is_anomaly: bool
    fault_id: int | None          # 0 healthy, 1-9 faults, None if unknown
    fault_family: str
    fault: str                    # display name
    confidence: float             # 0-1
    top_features: list[tuple[str, float]] = []
    source: str


class RULResult(BaseModel):
    rul_seconds: float            # 0-RUL_CAP_S; RUL_CAP_S = "10 min or more"
    rul_low: float | None = None  # optional confidence band
    rul_high: float | None = None
    source: str


class FaultModel(Protocol):
    def predict(self, window: list[dict]) -> FaultResult: ...


class RULModel(Protocol):
    def predict(self, history: list[dict]) -> RULResult | None: ...


# ---------------------------------------------------------------------------
# Rule-based stand-ins
# ---------------------------------------------------------------------------

# Health below which the stand-in calls the engine anomalous.
ANOMALY_HEALTH = 80

# Signal checks used to tell faults of the same subsystem apart.
EGT_OVERHEAT_C = 40       # EGT above expected: overheating, not cooling
OIL_SENSOR_C = 8.0        # oil above expected: real cooling loss, not a bad CHT sensor
RPM_ROUGH = 5.0           # RPM roughness well above healthy (~0.3)
RPM_DROP = 0.03           # RPM below expected: misfire, not instability
ENGINE_SLOW = 0.10        # RPM this far below expected: the engine is the cause

# Residual that counts as "1.0" when ranking the signals behind a call.
RESIDUAL_SCALE = {
    "rpm": 300.0,
    "egt": 80.0,
    "cht": 20.0,
    "oil_pressure": 5.0,
    "oil_temperature": 10.0,
    "battery_voltage": 1.0,
    "alternator_current": 4.0,
}

# Healthy limits of the window statistics (match backend/twin/service.py).
RPM_ROUGHNESS_LIMIT = 2.0
CHT_ROUGHNESS_LIMIT = 1.2
VIBRATION_RMS_LIMIT = 2.2


def roughness(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    return median(
        abs(values[i] - (values[i - 1] + values[i + 1]) / 2)
        for i in range(1, len(values) - 1)
    )


def rpm_deviation(samples: list[dict]) -> list[float]:
    """RPM minus expected healthy RPM (raw RPM if no baseline).

    Roughness is measured on this, so healthy throttle transients, which
    the baseline follows, don't look like rough running.
    """

    return [
        s["rpm"] - s.get("expected_rpm", 0.0)
        if "expected_rpm" in s else s["rpm"]
        for s in samples
    ]


def engine_health(sample: dict) -> float | None:
    """Weakest engine subsystem health of a sample (sensor excluded)."""

    scores = [
        sample.get(f"health_{name}")
        for name in SUBSYSTEMS
        if sample.get(f"health_{name}") is not None
    ]
    return min(scores) if scores else None


def diagnose(sample: dict, recent_rpm: list[float]) -> str:
    """Fault family of the weakest engine subsystem, from signal checks."""

    scores = {
        name: sample[f"health_{name}"]
        for name in SUBSYSTEMS
        if sample.get(f"health_{name}") is not None
    }
    weakest = min(scores, key=scores.get)

    def expected(name):
        return sample.get(f"expected_{name}", sample[name])

    expected_rpm = expected("rpm")
    rpm_drop = (expected_rpm - sample["rpm"]) / max(expected_rpm, 1.0)

    # A bus sagging because the engine is slow is an engine problem.
    if weakest == "electrical" and rpm_drop > ENGINE_SLOW:
        weakest = "combustion"

    if weakest == "lubrication":
        return "oil_pressure"
    if weakest == "thermal":
        if sample["egt"] - expected("egt") > EGT_OVERHEAT_C:
            return "overheating"
        # Real cooling loss also heats the oil (12+ °C above expected once
        # thermal health is low); a drifting CHT sensor reports a hot head
        # while the oil stays within a few degrees. Oil heats far slower
        # than the head, so compare it to a fixed margin, not to the CHT rise.
        hot_head = sample["cht"] - expected("cht")
        hot_oil = sample["oil_temperature"] - expected("oil_temperature")
        if hot_head > 0 and hot_oil < OIL_SENSOR_C:
            return "cht_sensor"
        return "cooling"
    if weakest == "combustion":
        if roughness(recent_rpm) > RPM_ROUGH:
            return "misfire" if rpm_drop > RPM_DROP else "instability"
        return "fuel_starvation"
    if weakest == "mechanical":
        return "vibration"
    if weakest == "injection":
        return "injector"
    if weakest == "electrical":
        return "electrical"
    return "unclassified"


class RuleFaultModel:
    """Stand-in fault model: health scores + signal checks.

    Anomaly score: how far the weakest health (sensor included) is below
    100, scaled so 1.0 is ANOMALY_HEALTH. Confidence is a heuristic that
    grows with the health deficit; the trained classifier gives real
    probabilities.
    """

    source = "rules"

    def predict(self, window: list[dict]) -> FaultResult:
        sample = window[-1]
        rough_window = window[-30:]

        scores = [
            sample.get(f"health_{name}")
            for name in SUBSYSTEMS + ("sensor",)
            if sample.get(f"health_{name}") is not None
        ]
        weakest = min(scores) if scores else 100.0
        anomaly_score = (100.0 - weakest) / (100.0 - ANOMALY_HEALTH)
        is_anomaly = anomaly_score >= 1.0

        if is_anomaly:
            engine = engine_health(sample)
            sensor = sample.get("health_sensor")
            if (
                sensor is not None
                and sensor < ANOMALY_HEALTH
                and (engine is None or engine >= ANOMALY_HEALTH)
            ):
                family = "cht_sensor"
            else:
                family = diagnose(sample, rpm_deviation(rough_window))
            confidence = min(0.99, 0.5 + (100.0 - weakest) / 100.0)
        else:
            family = "healthy"
            confidence = min(0.99, weakest / 100.0)

        fault_id = FAMILY_TO_ID.get(family)
        name = FAULTS[fault_id][1] if fault_id is not None else EXTRA_FAMILIES[family]

        return FaultResult(
            anomaly_score=round(anomaly_score, 3),
            is_anomaly=is_anomaly,
            fault_id=fault_id,
            fault_family=family,
            fault=name,
            confidence=round(confidence, 3),
            top_features=self._top_features(sample, rough_window),
            source=self.source,
        )

    @staticmethod
    def _top_features(sample, rough_window, limit=3):
        contributions = {}
        for name, scale in RESIDUAL_SCALE.items():
            if sample.get(name) is not None and f"expected_{name}" in sample:
                contributions[name] = abs(
                    sample[name] - sample[f"expected_{name}"]
                ) / scale

        rpm_rough = roughness(rpm_deviation(rough_window))
        cht_rough = roughness([s["cht"] for s in rough_window])
        vibration = [s["vibration"] for s in rough_window]
        rms = sqrt(sum(v * v for v in vibration) / len(vibration))
        contributions["rpm_roughness"] = rpm_rough / RPM_ROUGHNESS_LIMIT / 2
        contributions["cht_roughness"] = cht_rough / CHT_ROUGHNESS_LIMIT / 2
        contributions["vibration_rms"] = rms / VIBRATION_RMS_LIMIT / 2

        ranked = sorted(contributions.items(), key=lambda kv: -kv[1])
        return [(k, round(v, 2)) for k, v in ranked[:limit] if v >= 0.5]


class HealthTrendRULModel:
    """Stand-in RUL model (RUL_MODEL_GUIDE.md §6.1).

    Averages the weakest engine health over SMOOTHING_WINDOW samples, fits
    a line to the last TREND_SAMPLES averages and extends it to the failure
    threshold. No decline means RUL_CAP_S.
    """

    source = "health-trend"

    TREND_SAMPLES = 120
    MIN_DECLINE_PER_S = 0.02

    def predict(self, history: list[dict]) -> RULResult | None:
        needed = SMOOTHING_WINDOW + self.TREND_SAMPLES - 1
        weakest = [
            h for h in (engine_health(s) for s in history[-needed:])
            if h is not None
        ]
        if len(weakest) < 30:
            return None

        # Trailing averages for the last TREND_SAMPLES samples only.
        start = max(0, len(weakest) - self.TREND_SAMPLES)
        averaged = []
        for i in range(start, len(weakest)):
            window = weakest[max(0, i - SMOOTHING_WINDOW + 1):i + 1]
            averaged.append(sum(window) / len(window))

        if averaged[-1] < FAILURE_THRESHOLD:
            return RULResult(rul_seconds=0.0, rul_low=0.0, rul_high=0.0,
                             source=self.source)

        n = len(averaged)
        mean_t = (n - 1) / 2
        mean_h = sum(averaged) / n
        slope = sum(
            (i - mean_t) * (h - mean_h) for i, h in enumerate(averaged)
        ) / sum((i - mean_t) ** 2 for i in range(n))

        if slope > -self.MIN_DECLINE_PER_S:
            return RULResult(rul_seconds=RUL_CAP_S, source=self.source)

        eta = (averaged[-1] - FAILURE_THRESHOLD) / -slope
        if eta >= RUL_CAP_S:
            return RULResult(rul_seconds=RUL_CAP_S, source=self.source)

        # Rough band: a straight-line trend is optimistic for accelerating
        # faults, so the low side is wider.
        return RULResult(
            rul_seconds=round(eta),
            rul_low=round(0.6 * eta),
            rul_high=round(min(RUL_CAP_S, 1.2 * eta)),
            source=self.source,
        )


class XGBoostFaultModel:
    """Trained fault classifier (XGBoost, 10 classes) on 23 window features.

    Features come from twin/fault_features.py (reconstructed; see there).
    Test split: no missed faults, F1 0.93-1.00 except misfire (0.79).

    Class probabilities are averaged over the last SMOOTH_SAMPLES samples
    before choosing a fault: this lifts misfire F1 to 0.92 without slowing
    detection, because single samples of combustion instability can look
    like a misfire. Until the trained anomaly detector is usable, the
    classifier also gives the anomaly score: log2(1 / P(healthy)), so 1.0
    is the threshold (healthy at 50 %) and each halving of P(healthy) adds
    1 (25 % -> 2, 12.5 % -> 3), like the stand-in's open-ended scale.
    """

    source = "xgboost-v1"

    MODEL_PATH = Path(__file__).resolve().parent / "ml_models" / "fault" / "xgboost_classifier.json"
    SMOOTH_SAMPLES = 20
    MIN_PROBABILITY = 1e-6    # caps the anomaly score at ~20

    # Features -> the signal shown as "signals behind the call".
    FEATURE_SIGNAL = {
        "rpm_res": "rpm", "rpm_res_smooth": "rpm", "rpm_res_diff_60s": "rpm",
        "rpm_res_mean_60s": "rpm", "egt_res": "egt", "egt_res_diff_60s": "egt",
        "egt_res_mean_60s": "egt", "cht_res": "cht", "cht_diff_10s": "cht",
        "oil_press_res": "oil_pressure", "oil_press_res_diff_60s": "oil_pressure",
        "oil_press_res_mean_60s": "oil_pressure", "oil_temp_res": "oil_temperature",
        "battery_res": "battery_voltage", "fuel_ratio": "fuel_ratio",
        "vibration_diff_60s": "vibration_rms", "vibration_rms": "vibration_rms",
        "rpm_roughness": "rpm_roughness", "cht_roughness": "cht_roughness",
        "torque_roughness": "torque_roughness", "throttle_diff_60s": "throttle",
        "throttle": "throttle", "injection_duration": "injection_duration",
    }

    def __init__(self):
        import xgboost as xgb

        from twin import fault_features

        self._xgb = xgb
        self._features = fault_features
        self._booster = xgb.Booster()
        self._booster.load_model(str(self.MODEL_PATH))
        self._booster.set_param({"nthread": 1})
        if self._booster.feature_names != fault_features.FEATURE_COLUMNS:
            raise ValueError("Classifier features don't match fault_features.py")
        self._fallback = RuleFaultModel()

    def predict(self, window: list[dict]) -> FaultResult:
        import numpy as np
        import pandas as pd

        f = self._features
        if "expected_rpm" not in window[-1]:
            return self._fallback.predict(window)

        rows = window[-(f.LOOKBACK + self.SMOOTH_SAMPLES):]
        table = f.build_fault_features(pd.DataFrame(rows)).iloc[-self.SMOOTH_SAMPLES:]
        matrix = self._xgb.DMatrix(table.to_numpy(dtype=np.float32), feature_names=f.FEATURE_COLUMNS)
        probabilities = self._booster.predict(matrix).mean(axis=0)

        fault_id = int(probabilities.argmax())
        family, name = FAULTS[fault_id]
        anomaly_score = log2(1.0 / max(float(probabilities[0]), self.MIN_PROBABILITY))

        return FaultResult(
            anomaly_score=round(anomaly_score, 3),
            is_anomaly=fault_id != 0,
            fault_id=fault_id,
            fault_family=family,
            fault=name,
            confidence=round(float(probabilities[fault_id]), 3),
            top_features=self._top_features(table.iloc[[-1]], fault_id) if fault_id else [],
            source=self.source,
        )

    def _top_features(self, latest, fault_id, limit=3):
        """Signals that pushed the latest sample toward the fault (SHAP)."""

        import numpy as np

        matrix = self._xgb.DMatrix(latest.to_numpy(dtype=np.float32), feature_names=self._features.FEATURE_COLUMNS)
        contributions = self._booster.predict(matrix, pred_contribs=True)[0, fault_id, :-1]
        by_signal = {}
        for feature, value in zip(self._features.FEATURE_COLUMNS, contributions):
            if value > 0:
                signal = self.FEATURE_SIGNAL[feature]
                by_signal[signal] = by_signal.get(signal, 0.0) + float(value)
        total = sum(by_signal.values()) or 1.0
        ranked = sorted(by_signal.items(), key=lambda kv: -kv[1])
        return [(k, round(v / total, 2)) for k, v in ranked[:limit]]


class GRURULModel:
    """Trained RUL model: a GRU over 180 s of features, run with ONNX Runtime.

    Trained by rul-model-new/rul (prepare_data.py, train.py); the features
    come from twin/rul_features.py, the same code used for training. Test
    split: in-horizon RMSE 118 s vs 229 s for HealthTrendRULModel.

    Like the evaluation, the output is smoothed with a ~5 s exponential
    average. To stay stateless, the last SMOOTH_SAMPLES sequences are
    scored on every call and averaged.
    """

    source = "gru-v1"

    MODEL_DIR = Path(__file__).resolve().parent / "ml_models" / "rul_gru"
    SMOOTH_HALFLIFE_S = 5
    SMOOTH_SAMPLES = 25       # older samples weigh < 4 % at a 5 s half-life

    def __init__(self):
        import numpy as np
        import onnxruntime as ort

        from twin import rul_features

        self._np = np
        self._features = rul_features
        scaler = json.loads((self.MODEL_DIR / "scaler.json").read_text())
        if scaler["feature_names"] != rul_features.FEATURE_COLUMNS:
            raise ValueError("RUL scaler features don't match rul_features.py")
        if scaler["sequence_length"] != rul_features.SEQ_LEN:
            raise ValueError("RUL scaler sequence length doesn't match rul_features.py")
        self._mean = np.array(scaler["mean"], dtype=np.float32)
        self._std = np.array(scaler["std"], dtype=np.float32)

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1      # 1 Hz, tiny model: don't hog the CPU
        self._session = ort.InferenceSession(
            str(self.MODEL_DIR / "rul_gru.onnx"), options,
            providers=["CPUExecutionProvider"],
        )

    def predict(self, history: list[dict]) -> RULResult | None:
        import pandas as pd

        np = self._np
        f = self._features
        # The model scores nothing before warm-up plus the rolling window,
        # and needs the healthy baseline for its residuals.
        if len(history) < f.WARMUP + f.ROLL or "expected_rpm" not in history[-1]:
            return None

        table = f.build_features(pd.DataFrame(history))
        features = (table.to_numpy(dtype=np.float32) - self._mean) / self._std

        last = len(features) - 1
        ends = range(max(0, last - self.SMOOTH_SAMPLES + 1), last + 1)
        batch = np.stack([f.sequence_ending_at(features, e) for e in ends])
        raw = self._session.run(None, {"sequence": batch})[0] * RUL_CAP_S
        raw = np.clip(raw, 0.0, RUL_CAP_S)

        smoothed = pd.Series(raw).ewm(halflife=self.SMOOTH_HALFLIFE_S).mean()
        return RULResult(rul_seconds=round(float(smoothed.iloc[-1])), source=self.source)


def create_predictors() -> tuple[FaultModel, RULModel]:
    """The predictors the twin uses.

    Swap a stand-in for a trained model here once it is delivered (see the
    hand-back sections of ANOMALY_MODEL_GUIDE.md and RUL_MODEL_GUIDE.md).
    Each trained model falls back to its stand-in if it can't load.
    """

    try:
        fault_model = XGBoostFaultModel()
    except Exception:
        logger.exception("Trained fault model unavailable, using RuleFaultModel")
        fault_model = RuleFaultModel()

    try:
        rul_model = GRURULModel()
    except Exception:
        logger.exception("Trained RUL model unavailable, using HealthTrendRULModel")
        rul_model = HealthTrendRULModel()

    return fault_model, rul_model

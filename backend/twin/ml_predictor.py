from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from xgboost import XGBClassifier

from twin.ml import MLPredictor
from twin.ml_models.rul.predictor import predict_rul
from twin.schemas import MLPrediction


# ---------------------------------------------------------------------------
# Model paths
# ---------------------------------------------------------------------------

_MODEL_DIR = Path(__file__).parent / "ml_models" / "anomaly"

_AUTOENCODER_PATH = _MODEL_DIR / "autoencoder_anomaly_model.h5"
_SCALER_PATH = _MODEL_DIR / "autoencoder_scaler.pkl"
_THRESHOLD_PATH = _MODEL_DIR / "autoencoder_threshold.pkl"
_XGBOOST_PATH = _MODEL_DIR / "xgboost_fault_classifier_realistic.json"


# ---------------------------------------------------------------------------
# Feature definitions
# ---------------------------------------------------------------------------

# Feature names used by the trained anomaly/fault models.
FEATURES = [
    "Signal1_RPM",
    "Signal2_FuelFlow",
    "Signal3_Torque",
    "Signal4_OilTemp",
    "Signal5_OilPressure",
    "Signal6_CHT",
    "Signal8_EGT",
    "Signal9_Vibration",
    "Throttle",
    "EngineLoad",
    "Altitude_m",
    "AmbientTemp_C",
]

FAULT_NAMES = {
    0: "Healthy",
    1: "Torque Reduction",
    2: "Overheat",
    3: "Low Oil Pressure",
    4: "Fuel Flow Restriction",
}


# ---------------------------------------------------------------------------
# Load models once
# ---------------------------------------------------------------------------

_autoencoder_scaler = joblib.load(_SCALER_PATH)
_autoencoder_threshold = joblib.load(_THRESHOLD_PATH)

_autoencoder_model = tf.keras.models.load_model(
    _AUTOENCODER_PATH,
    compile=False,
)

_xgboost_model = XGBClassifier()
_xgboost_model.load_model(_XGBOOST_PATH)


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

class ModelPredictor(MLPredictor):

    def predict(
        self,
        telemetry_window: list[dict],
    ) -> MLPrediction:

        if not telemetry_window:
            raise ValueError("telemetry_window cannot be empty")

        # The anomaly/fault models predict from the latest telemetry sample.
        # The RUL model uses the full telemetry window.
        telemetry = telemetry_window[-1]

        # -------------------------------------------------------------------
        # Map Backend telemetry -> model input
        # -------------------------------------------------------------------

        rpm = telemetry["rpm"]
        fuel_flow = telemetry["fuel_flow"]
        torque = telemetry["torque"]
        oil_temperature = telemetry["oil_temperature"]
        oil_pressure = telemetry["oil_pressure"]
        cht = telemetry["cht"]
        egt = telemetry["egt"]
        vibration = telemetry["vibration"]

        throttle = telemetry["throttle"]
        engine_load = telemetry["engine_load"]
        altitude = telemetry["altitude"]
        ambient_temperature = telemetry["ambient_temperature"]

        # -------------------------------------------------------------------
        # Derived features used by the trained models
        # -------------------------------------------------------------------

        cht_above_ambient = cht - ambient_temperature

        cht_oiltemp_ratio = (
            cht / (oil_temperature + 1e-6)
        )

        # -------------------------------------------------------------------
        # Build model input
        # -------------------------------------------------------------------

        xgb_features = pd.DataFrame(
            [[
                rpm,
                fuel_flow,
                torque,
                oil_temperature,
                oil_pressure,
                cht,
                egt,
                vibration,
                cht_above_ambient,
                cht_oiltemp_ratio,
                throttle,
                engine_load,
                altitude,
                ambient_temperature,
            ]],
            columns=[
                "Signal1_RPM",
                "Signal2_FuelFlow",
                "Signal3_Torque",
                "Signal4_OilTemp",
                "Signal5_OilPressure",
                "Signal6_CHT",
                "Signal8_EGT",
                "Signal9_Vibration",
                "CHT_above_Ambient",
                "CHT_OilTemp_Ratio",
                "Throttle",
                "EngineLoad",
                "Altitude_m",
                "AmbientTemp_C",
            ],
        )

        input_scaled = _autoencoder_scaler.transform(
            xgb_features
        )

        # -------------------------------------------------------------------
        # Anomaly detection
        # -------------------------------------------------------------------

        reconstruction = _autoencoder_model.predict(
            input_scaled,
            verbose=0,
        )

        anomaly_score = float(
            np.mean(
                np.power(
                    input_scaled - reconstruction,
                    2,
                )
            )
        )

        is_anomaly = bool(
            anomaly_score > _autoencoder_threshold
        )

        # -------------------------------------------------------------------
        # XGBoost fault classification
        # -------------------------------------------------------------------

        fault_id = int(
            _xgboost_model.predict(xgb_features)[0]
        )

        probabilities = _xgboost_model.predict_proba(
            xgb_features
        )[0]

        fault_name = FAULT_NAMES.get(
            fault_id,
            "Unknown",
        )

        confidence = float(
            probabilities[fault_id]
        )

        # Healthy = no fault
        fault = (
            None
            if fault_id == 0
            else fault_name
        )

        # -------------------------------------------------------------------
        # RUL prediction
        # -------------------------------------------------------------------

        rul_hours = predict_rul(
            telemetry_window,
        )

        print(
            f"[ML] rul_hours={rul_hours}"
        )

        return MLPrediction(
            anomaly_score=anomaly_score,
            fault=fault,
            confidence=confidence,
            rul_hours=rul_hours,
        )
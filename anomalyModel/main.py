from pydantic import BaseModel
from typing import List, Dict, Any
import joblib
import numpy as np
import tensorflow as tf
from xgboost import XGBClassifier
import os

# Define the input features in the correct order
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
    "AmbientTemp_C"
]

# Fault class names as per README
FAULT_NAMES = {
    0: "Healthy",
    1: "Torque Reduction",
    2: "Overheat",
    3: "Low Oil Pressure",
    4: "Fuel Flow Restriction"
}

# Load models
current_dir = os.path.dirname(os.path.abspath(__file__))
try:
    # Autoencoder model, scaler, and threshold
    autoencoder_scaler = joblib.load(os.path.join(current_dir, "autoencoder_scaler.pkl"))
    autoencoder_threshold = joblib.load(os.path.join(current_dir, "autoencoder_threshold.pkl"))
    autoencoder_model = tf.keras.models.load_model(os.path.join(current_dir, "autoencoder_anomaly_model.h5"), compile=False)
    
    # XGBoost classifier
    xgboost_model = XGBClassifier()
    xgboost_model.load_model(
        os.path.join(current_dir, "xgboost_fault_classifier_realistic.json")
    )
except Exception as e:
    raise RuntimeError(f"Failed to load models: {e}")

class EngineTelemetry(BaseModel):
    Signal1_RPM: float
    Signal2_FuelFlow: float
    Signal3_Torque: float
    Signal4_OilTemp: float
    Signal5_OilPressure: float
    Signal6_CHT: float
    Signal8_EGT: float
    Signal9_Vibration: float
    Throttle: float
    EngineLoad: float
    Altitude_m: float
    AmbientTemp_C: float

def predict(telemetry: EngineTelemetry) -> Dict[str, Any]:
    """
    Predict anomaly and fault class for given engine telemetry.
    """
    # Calculate derived features for XGBoost and Autoencoder
    cht_above_ambient = telemetry.Signal6_CHT - telemetry.AmbientTemp_C
    cht_oiltemp_ratio = telemetry.Signal6_CHT / (telemetry.Signal4_OilTemp + 1e-6)
    
    xgb_features = [
        telemetry.Signal1_RPM,
        telemetry.Signal2_FuelFlow,
        telemetry.Signal3_Torque,
        telemetry.Signal4_OilTemp,
        telemetry.Signal5_OilPressure,
        telemetry.Signal6_CHT,
        telemetry.Signal8_EGT,
        telemetry.Signal9_Vibration,
        cht_above_ambient,
        cht_oiltemp_ratio,
        telemetry.Throttle,
        telemetry.EngineLoad,
        telemetry.Altitude_m,
        telemetry.AmbientTemp_C
    ]
    input_data_xgb = np.array([xgb_features])
    
    # Autoencoder anomaly detection
    input_scaled = autoencoder_scaler.transform(input_data_xgb)
    reconstruction = autoencoder_model.predict(input_scaled, verbose=0)
    anomaly_score = np.mean(np.power(input_scaled - reconstruction, 2))
    is_anomaly = bool(anomaly_score > autoencoder_threshold)
    
    # XGBoost fault classification
    fault_id = int(xgboost_model.predict(input_data_xgb)[0])
    fault_name = FAULT_NAMES.get(fault_id, "Unknown")
    probabilities = xgboost_model.predict_proba(input_data_xgb)[0].tolist()
    
    return {
        "anomaly_score": float(anomaly_score),
        "is_anomaly": is_anomaly,
        "fault_id": fault_id,
        "fault_name": fault_name,
        "probabilities": probabilities
    }

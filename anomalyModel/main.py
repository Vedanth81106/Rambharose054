from pydantic import BaseModel
from typing import List, Dict, Any
import joblib
import numpy as np
import os
import warnings
from collections import deque
import pandas as pd

# Suppress TensorFlow C++ logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
# Suppress specific sklearn warnings about feature names
warnings.filterwarnings("ignore", message="X does not have valid feature names")

import tensorflow as tf
from xgboost import XGBClassifier

# Fault class names as per new V2 Model
FAULT_NAMES = {
    0: "Healthy",
    1: "Torque Reduction",
    2: "Overheat",
    3: "Low Oil Pressure",
    4: "Fuel Flow Restriction",
    5: "Spark Plug Degradation",
    6: "Air Filter Clogged",
    7: "Fuel Injector Partial Block",
    8: "Combustion Instability",
    9: "Bearing Wear (Vibration)"
}

current_dir = os.path.dirname(os.path.abspath(__file__))

# Load models
try:
    # Autoencoder model, scaler, and threshold
    autoencoder_scaler = joblib.load(os.path.join(current_dir, "../../ML-workstation/autoencoder_scaler_v4.pkl"))
    try:
        autoencoder_threshold = float(joblib.load(os.path.join(current_dir, "../../ML-workstation/autoencoder_threshold_v4.pkl")))
    except:
        autoencoder_threshold = 1.11
    autoencoder_model = tf.keras.models.load_model(os.path.join(current_dir, "../../ML-workstation/autoencoder_anomaly_model_v4.h5"), compile=False)
    
    # XGBoost v2 classifier
    xgboost_model = XGBClassifier()
    # Loading directly from the ML-workstation directory where we trained it
    xgboost_model.load_model(os.path.join(current_dir, "../../ML-workstation/xgboost_new_classifier.json"))
except Exception as e:
    raise RuntimeError(f"Failed to load models: {e}")

# Global rolling buffer to store 60 seconds of history for the V2 features
telemetry_buffer = deque(maxlen=60)

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
    # --- NEW REQUIRED FIELDS FOR V2 MODEL ---
    Injection_Duration: float
    BatteryVoltage: float
    Expected_RPM: float
    Expected_EGT: float
    Expected_CHT: float
    Expected_OilPressure: float
    Expected_OilTemp: float
    Expected_BatteryVoltage: float

def predict(telemetry: EngineTelemetry) -> Dict[str, Any]:
    """
    Predict anomaly and fault class for given engine telemetry using V2 model.
    """
    # Append to rolling buffer
    telemetry_buffer.append(telemetry.dict())
    
    # Create DataFrame from buffer for easy rolling calculations
    df = pd.DataFrame(list(telemetry_buffer))
    
    # 1. Compute Base Residuals
    df['rpm_res'] = df['Signal1_RPM'] - df['Expected_RPM']
    df['egt_res'] = df['Signal8_EGT'] - df['Expected_EGT']
    df['cht_res'] = df['Signal6_CHT'] - df['Expected_CHT']
    df['oil_press_res'] = df['Signal5_OilPressure'] - df['Expected_OilPressure']
    df['oil_temp_res'] = df['Signal4_OilTemp'] - df['Expected_OilTemp']
    df['battery_res'] = df['BatteryVoltage'] - df['Expected_BatteryVoltage']
    
    df['fuel_ratio'] = df['Signal2_FuelFlow'] / (df['Injection_Duration'] + 1e-6)
    
    # 2. Rolling features (using min_periods=1 to handle early data)
    df['rpm_res_smooth'] = df['rpm_res'].rolling(window=10, min_periods=1).mean()
    df['cht_diff_10s'] = df['Signal6_CHT'] - df['Signal6_CHT'].shift(10).bfill()
    
    for col, src in [('rpm_res_diff_60s', 'rpm_res'), ('egt_res_diff_60s', 'egt_res'), 
                     ('oil_press_res_diff_60s', 'oil_press_res'), ('vibration_diff_60s', 'Signal9_Vibration'), 
                     ('throttle_diff_60s', 'Throttle')]:
        df[col] = df[src] - df[src].shift(60).bfill()
        
    for col, src in [('rpm_res_diff_5s', 'rpm_res'), ('egt_res_diff_5s', 'egt_res'), ('oil_press_res_diff_5s', 'oil_press_res')]:
        df[col] = df[src] - df[src].shift(5).bfill()
        
    df['vibration_rms_5s'] = np.sqrt((df['Signal9_Vibration']**2).rolling(window=5, min_periods=1).mean())
    
    for col, src in [('rpm_res_mean_60s', 'rpm_res'), ('egt_res_mean_60s', 'egt_res'), ('oil_press_res_mean_60s', 'oil_press_res')]:
        df[col] = df[src].rolling(window=60, min_periods=1).mean()
        
    df['vibration_rms'] = np.sqrt((df['Signal9_Vibration']**2).rolling(window=30, min_periods=1).mean())
    
    for prefix, src in [('rpm', 'rpm_res'), ('cht', 'Signal6_CHT'), ('torque', 'Signal3_Torque')]:
        point_rough = (df[src] - (df[src].shift(1) + df[src].shift(-1)) / 2).abs()
        df[f'{prefix}_roughness'] = point_rough.rolling(window=30, min_periods=1).median()
        df[f'{prefix}_roughness'] = df[f'{prefix}_roughness'].bfill().ffill()
        
    # Extract the features for the current (latest) timestep
    latest = df.iloc[-1]
    
    # -------------------------------------------------------------
    # Both Models use the 27 V2 Features
    # -------------------------------------------------------------
    xgb_v2_feature_names = [
        'rpm_res', 'egt_res', 'cht_res', 'oil_press_res', 'oil_temp_res', 'battery_res',
        'fuel_ratio', 'rpm_res_smooth', 'cht_diff_10s',
        'rpm_res_diff_60s', 'egt_res_diff_60s', 'oil_press_res_diff_60s', 'vibration_diff_60s', 'throttle_diff_60s',
        'rpm_res_diff_5s', 'egt_res_diff_5s', 'oil_press_res_diff_5s', 'vibration_rms_5s',
        'rpm_res_mean_60s', 'egt_res_mean_60s', 'oil_press_res_mean_60s',
        'vibration_rms', 'rpm_roughness', 'cht_roughness', 'torque_roughness',
        'throttle', 'injection_duration'
    ]
    
    latest['throttle'] = latest['Throttle']
    latest['injection_duration'] = latest['Injection_Duration']
    
    # Base array for both models
    base_features = latest[xgb_v2_feature_names].values.astype(float).reshape(1, -1)
    
    # -------------------------------------------------------------
    # Model 1: Autoencoder
    # -------------------------------------------------------------
    ae_feature_names = [
        'rpm_res', 'egt_res', 'cht_res', 'oil_press_res', 'oil_temp_res', 'battery_res',
        'fuel_ratio', 'rpm_res_smooth', 'cht_diff_10s',
        'rpm_res_diff_5s', 'egt_res_diff_5s', 'oil_press_res_diff_5s', 'vibration_rms_5s',
        'rpm_res_mean_60s', 'egt_res_mean_60s', 'oil_press_res_mean_60s',
        'vibration_rms', 'rpm_roughness', 'cht_roughness', 'torque_roughness',
        'throttle', 'injection_duration'
    ]
    ae_base_features = latest[ae_feature_names].values.astype(float).reshape(1, -1)
    
    # Calculate Vibration/Throttle Ratio for the Autoencoder
    vib = latest['vibration_rms'].values[0]
    thr_diff = latest['throttle_diff_60s'].values[0]
    vib_ratio = vib / (np.abs(thr_diff) + 1.0)
    
    # Autoencoder expects 23 features
    ae_features = np.append(ae_base_features, [[vib_ratio]], axis=1)
    
    input_scaled = autoencoder_scaler.transform(ae_features)
    reconstruction = autoencoder_model.predict(input_scaled, verbose=0)
    anomaly_score = float(np.mean(np.power(input_scaled - reconstruction, 2)))
    is_anomaly = bool(anomaly_score > autoencoder_threshold)
    
    # -------------------------------------------------------------
    # Model 2: XGBoost V2 Fault Classifier
    # -------------------------------------------------------------
    # XGBoost expects 23 features (excludes the four 5s features)
    xgb_feature_names_23 = [
        'rpm_res', 'egt_res', 'cht_res', 'oil_press_res', 'oil_temp_res', 'battery_res',
        'fuel_ratio', 'rpm_res_smooth', 'cht_diff_10s',
        'rpm_res_diff_60s', 'egt_res_diff_60s', 'oil_press_res_diff_60s', 'vibration_diff_60s', 'throttle_diff_60s',
        'rpm_res_mean_60s', 'egt_res_mean_60s', 'oil_press_res_mean_60s',
        'vibration_rms', 'rpm_roughness', 'cht_roughness', 'torque_roughness',
        'throttle', 'injection_duration'
    ]
    xgb_v2_input_raw = latest[xgb_feature_names_23].values.astype(float).reshape(1, -1)
    
    # CRITICAL: Apply the Log Transform that the V2 model was trained on!
    xgb_v2_input = np.sign(xgb_v2_input_raw) * np.log1p(np.abs(xgb_v2_input_raw))
    
    probs = xgboost_model.predict_proba(xgb_v2_input)[0]
    
    # Apply the exact flat 20% threshold from evaluate_xgboost_v2.py
    thresholds = np.array([0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.20])
    fault_probs = probs[1:]
    
    valid_faults = np.where(fault_probs > thresholds)[0]
    
    if len(valid_faults) > 0:
        # Out of the faults that crossed the 20% threshold, pick the highest probability
        best_fault_idx = valid_faults[np.argmax(fault_probs[valid_faults])]
        fault_id = int(best_fault_idx + 1)
    else:
        fault_id = 0
        
    fault_name = FAULT_NAMES.get(fault_id, "Unknown")
    
    return {
        "anomaly_score": anomaly_score,
        "is_anomaly": is_anomaly,
        "fault_id": fault_id,
        "fault_name": fault_name,
        "probabilities": probs.tolist()
    }

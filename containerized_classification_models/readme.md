# Aero Engine ML Models

## 1. Summary of Folder Contents
This directory contains the machine learning models and the prediction script used for the AI-Enabled Real-Time Digital Twin System. 

It provides a single entry point `main.py` containing a `predict()` method that takes engine telemetry data and returns an anomaly score (using an Autoencoder) and a specific fault classification (using XGBoost).


# Note : Run the test_predict.py to check the model input and output , First install the dependencies and then run it from this folder only 

## 2. Models and Files
This folder relies on two complementary models to detect anomalies and classify faults.

### Autoencoder Anomaly Detector
Detects if the engine is behaving abnormally by learning normal engine behavior.
- `autoencoder_anomaly_model.h5`: The trained Autoencoder TensorFlow/Keras model.
- `autoencoder_scaler.pkl`: The StandardScaler used to normalize input features before passing them to the Autoencoder.
- `autoencoder_threshold.pkl`: The decision threshold for the anomaly score.

### XGBoost Fault Classifier
Identifies the specific known fault type if an issue occurs.
- `xgboost_fault_classifier_realistic.json`: The trained XGBoost model file that predicts the fault class probabilities based on engine telemetry.

### Unused Models (Artifacts)
Older or unused models (like Isolation Forest and previous versions of XGBoost) have been moved to the `artifacts/` folder and added to `.gitignore`.

## 3. Sample Input
The models expect an `EngineTelemetry` object with 12 features. You can invoke the `predict` method from `main.py` by providing the following sample input:

```python
from main import EngineTelemetry, predict

sample_data = EngineTelemetry(
    Signal1_RPM=2000.0,
    Signal2_FuelFlow=15.0,
    Signal3_Torque=120.0,
    Signal4_OilTemp=80.0,
    Signal5_OilPressure=40.0,
    Signal6_CHT=150.0,
    Signal8_EGT=700.0,
    Signal9_Vibration=1.5,
    Throttle=50.0,
    EngineLoad=60.0,
    Altitude_m=1000.0,
    AmbientTemp_C=20.0
)
```

## 4. Sample Output
When you pass the sample input to the `predict(sample_data)` method, you will receive a dictionary response with the following format:

```json
{
  "anomaly_score": 7670.588862651703,
  "is_anomaly": true,
  "fault_id": 1,
  "fault_name": "Torque Reduction",
  "probabilities": [
    0.0000252799,
    0.7577714920,
    0.0005807185,
    0.0000011770,
    0.2416213303
  ]
}
```

- **`anomaly_score`**: The reconstruction error from the Autoencoder.
- **`is_anomaly`**: Boolean indicating if the score exceeded the healthy threshold.
- **`fault_id`**: The ID of the predicted fault (0 = Healthy, 1 = Torque Reduction, 2 = Overheat, 3 = Low Oil Pressure, 4 = Fuel Flow Restriction).
- **`fault_name`**: The human-readable name of the predicted fault.
- **`probabilities`**: A list of confidence scores (probabilities) for each of the 5 fault classes.

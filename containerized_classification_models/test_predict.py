from main import EngineTelemetry, predict
import json

def test():
    # Create sample dummy engine telemetry data
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

    print("--- Input Telemetry Data ---")
    print(sample_data.model_dump_json(indent=2))
    
    print("\n--- Running Prediction ---")
    try:
        result = predict(sample_data)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Prediction failed with error: {e}")

if __name__ == "__main__":
    test()

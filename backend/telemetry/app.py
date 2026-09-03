import paho.mqtt.client as mqtt
from pydantic import ValidationError

from config import BROKER_HOST, BROKER_PORT, MQTT_TOPIC
from database import SessionLocal
from repository import TelemetryRepository
from schemas import TelemetryCreate
from service import TelemetryService

from twin.factory import create_digital_twin_service
from twin.ml_predictor import ModelPredictor

repository = TelemetryRepository()
service = TelemetryService(repository)

twin_service = create_digital_twin_service(
    ModelPredictor()
)


def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties,
):
    print("Connected to MQTT broker")

    client.subscribe(MQTT_TOPIC)

    print(f"Subscribed to: {MQTT_TOPIC}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        telemetry = TelemetryCreate.model_validate_json(payload)

    except UnicodeDecodeError:
        print("Invalid UTF-8 payload")
        return

    except ValidationError as error:
        print(f"Invalid telemetry: {error}")
        return

    try:
        with SessionLocal.begin() as session:
            stored = service.process(
                session,
                telemetry,
                msg.topic,
            )

            if stored:
                print(
                    f"Telemetry stored: "
                    f"{telemetry.engine_id}"
                )

                state = twin_service.process(
                    session,
                    telemetry,
                )

                if state:
                    print(
                        f"Twin state: "
                        f"{state.operating_state} "
                        f"health={state.health.overall}"
                    )

            else:
                print(
                    f"Duplicate telemetry ignored: "
                    f"{telemetry.engine_id}"
                )

    except ValueError as error:
        print(f"Invalid telemetry: {error}")

    except Exception as error:
        print(f"Telemetry processing failed: {error}")


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2
    )

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(
        BROKER_HOST,
        BROKER_PORT,
    )

    print("Waiting for telemetry...")

    try:
        client.loop_forever()
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
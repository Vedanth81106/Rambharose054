import os

from dotenv import load_dotenv


load_dotenv()


BROKER_HOST = os.getenv(
    "MQTT_BROKER_HOST",
    "localhost",
)

BROKER_PORT = int(
    os.getenv(
        "MQTT_BROKER_PORT",
        "1883",
    )
)

MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "engine/+/telemetry",
)
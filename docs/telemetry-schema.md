# Telemetry Schema v1

## MQTT Topic

engine/{engine_id}/telemetry

Example:

engine/ENG-001/telemetry

## Payload

| Field | Type | Unit | Required |
|---|---|---|---|
| timestamp | string | ISO-8601 UTC | Yes |
| engine_id | string | - | Yes |
| mission_id | string | - | Yes |
| rpm | float | RPM | Yes |
| cht | float | °C | Yes |
| egt | float | °C | Yes |
| oil_pressure | float | TBD | Yes |
| oil_temperature | float | °C | Yes |
| fuel_flow | float | TBD | Yes |
| vibration | float | TBD | Yes |
| battery_voltage | float | V | Yes |
| alternator_current | float | A | Yes |
| injection_timing | float | degrees | Yes |

## Example Payload

{
  "timestamp": "2026-08-27T16:00:00.123Z",
  "engine_id": "ENG-001",
  "mission_id": "MISSION-001",
  "rpm": 2450.0,
  "cht": 175.2,
  "egt": 680.4,
  "oil_pressure": 52.1,
  "oil_temperature": 91.3,
  "fuel_flow": 21.4,
  "vibration": 0.31,
  "battery_voltage": 27.8,
  "alternator_current": 42.0,
  "injection_timing": 18.2
}
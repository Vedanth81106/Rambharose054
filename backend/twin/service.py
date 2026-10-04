from datetime import datetime
from math import sqrt
from statistics import median

from sqlalchemy.orm import Session

from telemetry.repository import TelemetryRepository
from telemetry.schemas import TelemetryCreate

from twin import baseline
from twin.advisory import AdvisoryEngine
from twin.models import HealthSnapshot
from twin.failure import FAILURE_THRESHOLD, SMOOTHING_WINDOW
from twin.predictor import (
    RUL_CAP_S,
    RUL_HISTORY_SAMPLES,
    FaultModel,
    RULModel,
    RULResult,
    engine_health,
)
from twin.repository import HealthSnapshotRepository
from twin.schemas import (
    DigitalTwinState,
    HealthState,
    MLPrediction,
)


# Healthy readings at the nominal cruise point (full throttle, 50 % load,
# sea level, 25 degC, warmed up), where the fixed limits below were
# calibrated. When the healthy baseline (twin/baseline.py) is available,
# each limit moves by (expected now - this reference), so health measures
# the deviation from a healthy engine in the same flight conditions.
CRUISE_REFERENCE = {
    "rpm": 3993.94,
    "egt": 709.15,
    "cht": 80.13,
    "oil_pressure": 59.37,
    "oil_temperature": 105.73,
    "battery_voltage": 28.0,
    "alternator_current": 12.47,
}


# Subsystem health scores, in the order the model samples carry them.
HEALTH_FIELDS = (
    "thermal",
    "combustion",
    "lubrication",
    "mechanical",
    "electrical",
    "injection",
    "sensor",
)


# Electrical health limits. They mirror the Simulink Electrical_Model
# parameters in simulation/engine_params.m (elec.*).
#
# Healthy: the alternator carries the 28 V bus (elec.V_bus_reg) and supplies
# at least the avionics load (elec.I_avionics = 10 A, 1 A sensor margin).
BUS_VOLTAGE_MIN_V = 27.0
BUS_VOLTAGE_MAX_V = 29.5
ALTERNATOR_CURRENT_MIN_A = 9.0
ALTERNATOR_CURRENT_MAX_A = 25.0   # elec.I_alt_max (rated output)


# ECU injection parameters. They mirror the Simulink Injection_Model
# parameters in simulation/engine_params.m (inj.*).
#
# Start-of-injection map (deg BTDC). Rows = INJ_RPM_BP, columns =
# INJ_THROTTLE_BP. Linear interpolation, clipped at the map edges.
INJ_RPM_BP = (1500, 3000, 4500, 6000, 7500)
INJ_THROTTLE_BP = (0.0, 0.25, 0.5, 0.75, 1.0)
INJ_TIMING_TABLE = (
    (12, 11, 10, 9, 8),
    (16, 15, 14, 13, 12),
    (20, 19, 18, 17, 16),
    (23, 22, 21, 20, 19),
    (26, 25, 24, 23, 22),
)
INJ_N_CYL = 1
INJ_STROKES = 4
INJ_Q_STATIC_GPS = 2.5     # injector static flow rate (g/s)
INJ_T_DEAD_MS = 0.8        # opening dead time added to every pulse (ms)
INJ_RPM_MIN = 300          # below this speed the ECU does not inject

# Healthy: reported values match the ECU map / measured fuel flow within
# the sensor noise and lag (timing ~0.1 deg; fuel flow ~0.15 kg/h, which
# is a large fraction of the flow at low throttle).
INJ_TIMING_TOLERANCE_DEG = 1.0
INJ_FUEL_TOLERANCE = 0.05       # relative to the commanded fuel flow
INJ_FUEL_NOISE_KGPH = 0.15      # absolute floor for the fuel tolerance


# Signal roughness (median |second difference| over ROUGHNESS_WINDOW
# samples). Real engine temperatures and speed change smoothly, even
# through throttle transitions, so sample-to-sample jitter points at
# combustion instability (RPM) or a failing sensor (CHT). Healthy limits
# come from simulator runs incl. rapid throttle transitions: RPM <= 0.75,
# CHT <= 1.0.
ROUGHNESS_WINDOW = 30
RPM_ROUGHNESS_LIMIT = 2.0       # RPM
CHT_ROUGHNESS_LIMIT = 1.2       # degC

# Vibration RMS over ROUGHNESS_WINDOW samples. Healthy simulator runs stay
# <= 2.1 (incl. every non-vibration fault); imbalance / bearing wear
# grows it to ~6.
VIBRATION_RMS_LIMIT = 2.2


class DigitalTwinService:

    def __init__(
        self,
        repository: HealthSnapshotRepository,
        telemetry_repository: TelemetryRepository,
        fault_model: FaultModel,
        rul_model: RULModel,
    ):
        self.repository = repository
        self.telemetry_repository = telemetry_repository
        self.fault_model = fault_model
        self.rul_model = rul_model
        self.advisor = AdvisoryEngine()

    def process(
        self,
        session: Session,
        telemetry: TelemetryCreate,
    ) -> DigitalTwinState | None:

        # The healthy baseline needs the operating-condition history; the
        # other checks use the latest 60 samples of it.
        history_records = (
            self.telemetry_repository.get_latest_window(
                session,
                telemetry.engine_id,
                telemetry.mission_id,
                limit=baseline.HISTORY_SAMPLES,
            )
        )

        if len(history_records) < 60:
            return None

        telemetry_records = history_records[-60:]

        # Expected healthy readings for every sample. A shorter history
        # than requested covers the whole mission, so the baseline can
        # follow the engine from a cold start.
        expected_rows = baseline.expected_series(
            [
                {
                    "throttle": item.throttle,
                    "engine_load": item.engine_load,
                    "altitude": item.altitude,
                    "ambient_temperature": item.ambient_temperature,
                }
                for item in history_records
            ],
            from_engine_start=(
                len(history_records) < baseline.HISTORY_SAMPLES
            ),
        )
        expected = expected_rows[-1] if expected_rows else None

        # get_latest_window() returns samples oldest first, so the last
        # samples here are the most recent readings.
        recent_records = telemetry_records[-10:]
        roughness_records = telemetry_records[-ROUGHNESS_WINDOW:]

        recent_vibration = [
            item.vibration
            for item in roughness_records
        ]

        recent_injection = [
            (
                item.rpm,
                item.throttle,
                item.fuel_flow,
                item.injection_timing,
                item.injection_duration,
            )
            for item in recent_records
        ]

        # RPM roughness is measured on the deviation from the expected
        # healthy RPM, so fast but healthy throttle transients (which the
        # baseline follows) don't count as rough running.
        if expected_rows:
            recent_rpm = [
                item.rpm - row["rpm"]
                for item, row in zip(
                    roughness_records,
                    expected_rows[-len(roughness_records):],
                )
            ]
        else:
            recent_rpm = [item.rpm for item in roughness_records]

        health = self.calculate_health(
            telemetry,
            recent_vibration=recent_vibration,
            recent_injection=recent_injection,
            recent_rpm=recent_rpm,
            recent_cht=[item.cht for item in roughness_records],
            expected=expected,
        )

        # Fault and RUL predictions (trained models or rule stand-ins,
        # twin/predictor.py) on dataset-shaped samples.
        samples = self._model_samples(
            session,
            history_records[-RUL_HISTORY_SAMPLES:],
            expected_rows[-RUL_HISTORY_SAMPLES:] if expected_rows else None,
            health,
        )
        fault = self.fault_model.predict(samples)
        rul = self.rul_model.predict(samples)

        # A countdown needs a confirmed fault: on healthy flight the trained
        # RUL model occasionally dips below the cap (3 % of healthy test
        # samples read < 400 s), which would raise a false advisory.
        if rul is not None and not fault.is_anomaly and rul.rul_seconds < RUL_CAP_S:
            rul = RULResult(rul_seconds=RUL_CAP_S, source=rul.source)

        # Once the failure definition is met (twin/failure.py), RUL is 0:
        # the trained model's output only gets down to a few seconds.
        recent = [
            h for h in (engine_health(s) for s in samples[-SMOOTHING_WINDOW:])
            if h is not None
        ]
        if (
            rul is not None
            and len(recent) == SMOOTHING_WINDOW
            and sum(recent) / len(recent) < FAILURE_THRESHOLD
        ):
            rul = RULResult(rul_seconds=0.0, source=rul.source)

        prediction = MLPrediction(
            anomaly_score=fault.anomaly_score,
            is_anomaly=fault.is_anomaly,
            fault_id=fault.fault_id,
            fault=fault.fault if fault.fault_id != 0 else None,
            confidence=fault.confidence,
            rul_seconds=rul.rul_seconds if rul else None,
            rul_low=rul.rul_low if rul else None,
            rul_high=rul.rul_high if rul else None,
            top_features=fault.top_features,
            source=f"{fault.source}+{rul.source}" if rul else fault.source,
        )

        state = DigitalTwinState(
            engine_id=telemetry.engine_id,
            mission_id=telemetry.mission_id,
            operating_state=self._determine_operating_state(
                health,
                prediction,
            ),
            health=health,
            prediction=prediction,
        )

        state.advisory = self.advisor.update(
            telemetry,
            health,
            fault,
            rul,
            expected=expected,
            recent_rpm=recent_rpm,
            recent_vibration=recent_vibration,
            commanded_fuel=(
                self._commanded_fuel_flow(
                    telemetry.rpm,
                    telemetry.injection_duration,
                )
                if telemetry.injection_duration is not None
                else None
            ),
        )

        self.save_health_snapshot(
            session,
            state,
            telemetry.timestamp,
        )

        return state

    def _model_samples(
        self,
        session: Session,
        records: list,
        expected_rows: list[dict] | None,
        current_health: HealthState,
    ) -> list[dict]:
        """Model input samples (dataset columns), oldest first.

        Health comes from the stored snapshots; the newest sample uses the
        health just computed (its snapshot isn't saved yet).
        """

        snapshots = self.repository.get_recent(
            session,
            records[-1].engine_id,
            records[-1].mission_id,
            len(records),
        )
        health_at = {snapshot.time: snapshot for snapshot in snapshots}

        samples = []
        for i, item in enumerate(records):
            sample = {
                name: getattr(item, name)
                for name in (
                    "throttle", "engine_load", "altitude",
                    "ambient_temperature", "rpm", "torque", "fuel_flow",
                    "cht", "egt", "oil_pressure", "oil_temperature",
                    "vibration", "battery_voltage", "alternator_current",
                    "injection_timing", "injection_duration",
                )
            }
            if expected_rows:
                for name, value in expected_rows[i].items():
                    sample[f"expected_{name}"] = value

            source = (
                current_health if i == len(records) - 1
                else health_at.get(item.time)
            )
            for name in HEALTH_FIELDS:
                sample[f"health_{name}"] = (
                    getattr(source, name) if source is not None else None
                )

            samples.append(sample)

        return samples

    def calculate_health(
        self,
        telemetry: TelemetryCreate,
        recent_vibration: list[float] | None = None,
        recent_injection: list[tuple] | None = None,
        recent_rpm: list[float] | None = None,
        recent_cht: list[float] | None = None,
        expected: dict[str, float] | None = None,
    ) -> HealthState:

        # How far each healthy reading sits from the cruise reference in
        # the current flight conditions (all zero without a baseline).
        shift = {
            name: (expected[name] - reference) if expected else 0.0
            for name, reference in CRUISE_REFERENCE.items()
        }

        thermal = self._thermal_health(telemetry, shift)
        combustion = self._combustion_health(
            telemetry,
            shift,
            recent_rpm=recent_rpm,
        )
        lubrication = self._lubrication_health(telemetry, shift)
        mechanical = self._mechanical_health(
            telemetry,
            recent_vibration=recent_vibration,
        )

        # None when the telemetry has no electrical / injection signals.
        electrical = self._electrical_health(telemetry, shift)
        injection = self._injection_health(
            telemetry,
            recent_injection=recent_injection,
        )

        # Instrumentation health. Not part of `overall`: a failing sensor
        # says the data is unreliable, not that the engine is degrading.
        # It still drives the operating state.
        sensor = self._sensor_health(recent_cht)

        # Average over the subsystems that have data, so older telemetry
        # without electrical / injection signals is not penalised.
        components = [
            score
            for score in (
                thermal,
                combustion,
                lubrication,
                mechanical,
                electrical,
                injection,
            )
            if score is not None
        ]

        overall = sum(components) / len(components)

        return HealthState(
            overall=round(overall, 2),
            thermal=thermal,
            combustion=combustion,
            lubrication=lubrication,
            mechanical=mechanical,
            electrical=electrical,
            injection=injection,
            sensor=sensor,
        )

    def save_health_snapshot(
        self,
        session: Session,
        state: DigitalTwinState,
        timestamp: datetime,
    ) -> HealthSnapshot:

        snapshot = HealthSnapshot(
            time=timestamp,
            engine_id=state.engine_id,
            mission_id=state.mission_id,

            overall=state.health.overall,
            thermal=state.health.thermal,
            combustion=state.health.combustion,
            lubrication=state.health.lubrication,
            mechanical=state.health.mechanical,
            electrical=state.health.electrical,
            injection=state.health.injection,
            sensor=state.health.sensor,

            anomaly_score=state.prediction.anomaly_score,
            is_anomaly=state.prediction.is_anomaly,
            fault_id=state.prediction.fault_id,
            fault=state.prediction.fault,
            confidence=state.prediction.confidence,
            rul_seconds=state.prediction.rul_seconds,
            rul_low=state.prediction.rul_low,
            rul_high=state.prediction.rul_high,
            top_features=[list(f) for f in state.prediction.top_features],
            prediction_source=state.prediction.source,

            advisory=(
                state.advisory.model_dump()
                if state.advisory is not None
                else None
            ),
        )

        return self.repository.save(
            session,
            snapshot,
        )

    def _thermal_health(
        self,
        telemetry: TelemetryCreate,
        shift: dict[str, float],
    ) -> float:

        # Healthy operating region at cruise (limits move with `shift`):
        # CHT <= 100°C
        # EGT <= 700°C

        cht_penalty = max(
            0,
            telemetry.cht - (100 + shift["cht"]),
        ) * 1.5

        egt_penalty = max(
            0,
            telemetry.egt - (700 + shift["egt"]),
        ) * 0.25

        return self._score(
            100
            - cht_penalty
            - egt_penalty
        )

    def _combustion_health(
        self,
        telemetry: TelemetryCreate,
        shift: dict[str, float],
        recent_rpm: list[float] | None = None,
    ) -> float:

        # Healthy RPM centered around the expected speed (~4000 RPM at
        # the cruise point).

        rpm_deviation = abs(
            telemetry.rpm - (4000 + shift["rpm"])
        )

        rpm_penalty = max(
            0,
            rpm_deviation - 300,
        ) * 0.04

        egt_deviation = abs(
            telemetry.egt - (650 + shift["egt"])
        )

        egt_penalty = max(
            0,
            egt_deviation - 80,
        ) * 0.10

        # Combustion instability: cycle-to-cycle torque variation makes
        # the RPM rough (3.5 points per RPM beyond the healthy limit).
        # recent_rpm is the deviation from the expected RPM when the
        # baseline is available, so throttle transients don't count.
        roughness_penalty = max(
            0,
            self._roughness(recent_rpm) - RPM_ROUGHNESS_LIMIT,
        ) * 3.5

        return self._score(
            100
            - rpm_penalty
            - egt_penalty
            - roughness_penalty
        )

    def _lubrication_health(
        self,
        telemetry: TelemetryCreate,
        shift: dict[str, float],
    ) -> float:

        # At cruise, healthy oil pressure is around 60 psi and oil
        # temperature around 100-105°C (limits move with `shift`).

        pressure_penalty = max(
            0,
            (55 + shift["oil_pressure"]) - telemetry.oil_pressure,
        ) * 3.0

        temperature_penalty = max(
            0,
            telemetry.oil_temperature - (115 + shift["oil_temperature"]),
        ) * 0.75

        return self._score(
            100
            - pressure_penalty
            - temperature_penalty
        )

    def _mechanical_health(
        self,
        telemetry: TelemetryCreate,
        recent_vibration: list[float] | None = None,
    ) -> float:

        # Vibration telemetry is a 1 Hz sample of a fast oscillating
        # signal, so single samples (and their signed median, which hovers
        # around zero) say little. The RMS over the latest samples tracks
        # the vibration amplitude.
        #
        # The raw vibration telemetry is NOT changed; only the health
        # calculation is smoothed.
        samples = recent_vibration or [telemetry.vibration]

        vibration_rms = sqrt(
            sum(value * value for value in samples) / len(samples)
        )

        # 40 points per unit of RMS beyond the healthy limit.
        vibration_penalty = max(
            0,
            vibration_rms - VIBRATION_RMS_LIMIT,
        ) * 40

        return self._score(
            100
            - vibration_penalty
        )

    def _electrical_health(
        self,
        telemetry: TelemetryCreate,
        shift: dict[str, float],
    ) -> float | None:

        # Older telemetry has no electrical signals.
        if (
            telemetry.battery_voltage is None
            or telemetry.alternator_current is None
        ):
            return None

        # Under-voltage: bus sagging toward battery voltage means the
        # alternator is no longer carrying the load (20 points per volt).
        # Over-voltage: regulator fault (25 points per volt).
        # The lower limits move with `shift` (at low engine speed a healthy
        # alternator delivers less); the upper ones are equipment ratings.
        voltage_penalty = (
            max(
                0,
                (BUS_VOLTAGE_MIN_V + shift["battery_voltage"])
                - telemetry.battery_voltage,
            ) * 20
            + max(0, telemetry.battery_voltage - BUS_VOLTAGE_MAX_V) * 25
        )

        # Alternator output below the avionics load drains the battery;
        # output above rating indicates an overloaded alternator.
        current_penalty = (
            max(
                0,
                (ALTERNATOR_CURRENT_MIN_A + shift["alternator_current"])
                - telemetry.alternator_current,
            ) * 4
            + max(0, telemetry.alternator_current - ALTERNATOR_CURRENT_MAX_A) * 4
        )

        return self._score(
            100
            - voltage_penalty
            - current_penalty
        )

    def _injection_health(
        self,
        telemetry: TelemetryCreate,
        recent_injection: list[tuple] | None = None,
    ) -> float | None:

        # Compares the reported ECU injection parameters with the rest of
        # the engine state:
        #   timing   -> start-of-injection map (RPM x throttle)
        #   duration -> the fuel flow the pulse width commands, against the
        #               measured fuel flow (a fouled injector delivers less
        #               fuel than the ECU commands)
        # A persistent mismatch points at injector or ECU timing faults.
        #
        # The median of the signed errors over the latest samples is used,
        # so symmetric sensor noise and the fuel-flow sensor lag during
        # throttle transitions cancel out and only a persistent bias
        # remains.
        samples = recent_injection or [
            (
                telemetry.rpm,
                telemetry.throttle,
                telemetry.fuel_flow,
                telemetry.injection_timing,
                telemetry.injection_duration,
            )
        ]

        timing_errors = []
        commanded_fuel = []
        fuel_errors = []

        for rpm, throttle, fuel_flow, timing, duration in samples:

            # Older telemetry has no injection signals, and the ECU does
            # not inject while the engine is stopped.
            if (
                timing is None
                or duration is None
                or rpm < INJ_RPM_MIN
            ):
                continue

            timing_errors.append(
                timing - self._expected_injection_timing(rpm, throttle)
            )

            commanded = self._commanded_fuel_flow(rpm, duration)
            commanded_fuel.append(commanded)
            fuel_errors.append(commanded - fuel_flow)

        if not timing_errors:
            return None

        # 10 points per degree beyond tolerance.
        timing_penalty = max(
            0,
            abs(median(timing_errors)) - INJ_TIMING_TOLERANCE_DEG,
        ) * 10

        # 4.5 points per percent of the commanded flow beyond tolerance.
        commanded = max(median(commanded_fuel), INJ_FUEL_NOISE_KGPH)
        fuel_tolerance = max(
            INJ_FUEL_TOLERANCE * commanded,
            INJ_FUEL_NOISE_KGPH,
        )
        fuel_penalty = max(
            0,
            abs(median(fuel_errors)) - fuel_tolerance,
        ) / commanded * 450

        return self._score(
            100
            - timing_penalty
            - fuel_penalty
        )

    @staticmethod
    def _expected_injection_timing(
        rpm: float,
        throttle: float,
    ) -> float:

        def locate(breakpoints, value):
            value = min(max(value, breakpoints[0]), breakpoints[-1])
            for i in range(len(breakpoints) - 2):
                if value <= breakpoints[i + 1]:
                    break
            else:
                i = len(breakpoints) - 2
            low, high = breakpoints[i], breakpoints[i + 1]
            return i, (value - low) / (high - low)

        r, fr = locate(INJ_RPM_BP, rpm)
        t, ft = locate(INJ_THROTTLE_BP, throttle)

        table = INJ_TIMING_TABLE
        low = table[r][t] + (table[r][t + 1] - table[r][t]) * ft
        high = table[r + 1][t] + (table[r + 1][t + 1] - table[r + 1][t]) * ft

        return low + (high - low) * fr

    @staticmethod
    def _commanded_fuel_flow(
        rpm: float,
        duration_ms: float,
    ) -> float:

        # Inverse of the ECU pulse-width calculation (kg/h):
        #   duration = 1000 * fuel_per_event / q_static + dead_time
        events_per_s = INJ_N_CYL * rpm / (60 * INJ_STROKES / 2)
        fuel_per_event_g = (
            max(0, duration_ms - INJ_T_DEAD_MS) * INJ_Q_STATIC_GPS / 1000
        )

        return fuel_per_event_g * events_per_s * 3600 / 1000

    def _sensor_health(
        self,
        recent_cht: list[float] | None,
    ) -> float | None:

        # A failing CHT thermocouple reads erratically; the true head
        # temperature cannot change that fast (time constant ~40 s).
        # 27 points per degC of jitter beyond the healthy limit.
        if not recent_cht or len(recent_cht) < 5:
            return None

        jitter_penalty = max(
            0,
            self._roughness(recent_cht) - CHT_ROUGHNESS_LIMIT,
        ) * 27

        return self._score(
            100
            - jitter_penalty
        )

    @staticmethod
    def _roughness(values: list[float] | None) -> float:

        # Median |x[i] - (x[i-1] + x[i+1]) / 2|: zero for straight lines
        # and slow curves (warm-up, throttle transitions), large for
        # sample-to-sample jitter.
        if not values or len(values) < 3:
            return 0.0

        return median(
            abs(values[i] - (values[i - 1] + values[i + 1]) / 2)
            for i in range(1, len(values) - 1)
        )

    @staticmethod
    def _score(value: float) -> float:

        return round(
            max(0, min(100, value)),
            2,
        )

    @staticmethod
    def _determine_operating_state(
        health: HealthState,
        prediction: MLPrediction,
    ) -> str:

        # A single failing subsystem must raise the state even when the
        # other subsystems keep the overall average high.
        weakest = min(
            score
            for score in (
                health.thermal,
                health.combustion,
                health.lubrication,
                health.mechanical,
                health.electrical,
                health.injection,
                health.sensor,
            )
            if score is not None
        )

        # Anomaly score in multiples of the detector's threshold
        # (predictors return it normalised).
        anomaly = prediction.anomaly_score
        fault_found = prediction.fault_id not in (None, 0)

        # An anomaly detector also reacts to unusual but healthy conditions
        # (e.g. engine warm-up), so on its own it can only raise a
        # WARNING. It escalates further only when the health indices or
        # the fault classifier confirm a problem.
        confirmed = (
            weakest < 80
            or health.overall < 80
            or fault_found
        )

        # A failing sensor misreads the engine but doesn't endanger it,
        # so it never makes the state CRITICAL (the advisory caps it too).
        sensor_fault = prediction.fault_id == 7

        if not sensor_fault and (
            health.overall < 40
            or (weakest < 30 and anomaly >= 3)
        ):
            return "CRITICAL"

        if (
            health.overall < 60
            or weakest < 30
            or (confirmed and anomaly >= 2)
        ):
            return "DEGRADED"

        if (
            health.overall < 80
            or weakest < 60
            or anomaly >= 1
            or fault_found
        ):
            return "WARNING"

        return "NOMINAL"

import { useEffect, useState } from "react";
import {
    AlertTriangle,
    Wifi,
} from "lucide-react";

import {
    startSimulation,
    stopSimulation,
    getSimulationStatus,
    injectFault,
} from "../../services/api";

import { useEngineData } from "../../hooks/useEngineData";
import { MISSION_PROFILES } from "../../missionProfiles";
import type { AdvisoryData } from "../../types/api";

const ADVISORY_COLOR: Record<AdvisoryData["level"], string> = {
    MONITOR: "#7fd4ff",
    CAUTION: "#eab308",
    WARNING: "#f97316",
    CRITICAL: "#e8543f",
};

// Pretty name of a signal in top_features.
const SIGNAL_LABEL: Record<string, string> = {
    rpm: "RPM",
    egt: "EGT",
    cht: "CHT",
    oil_pressure: "oil pressure",
    oil_temperature: "oil temperature",
    battery_voltage: "bus voltage",
    alternator_current: "alternator current",
    rpm_roughness: "RPM roughness",
    cht_roughness: "CHT jitter",
    vibration_rms: "vibration",
    fuel_ratio: "fuel ratio",
    torque_roughness: "torque roughness",
    throttle: "throttle",
    injection_duration: "injector pulse",
};

function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return m > 0 ? `${m} min ${s} s` : `${s} s`;
}

// Prediction source is "<fault model>+<RUL model>" (backend/twin/predictor.py);
// the rule-based stand-ins are labelled so a trained model is never assumed.
const STAND_INS = ["rules", "health-trend"];

function describeSource(source: string): string {
    const [fault, rul] = source.split("+");
    const part = (label: string, name?: string) =>
        name
            ? `${label} ${name.toUpperCase()} (${STAND_INS.includes(name) ? "RULE-BASED STAND-IN" : "TRAINED MODEL"})`
            : null;
    return [part("FAULT:", fault), part("RUL:", rul)].filter(Boolean).join(" · ");
}

function formatRul(prediction: {
    rul_seconds: number | null;
    rul_low?: number | null;
    rul_high?: number | null;
}): string {
    const rul = prediction.rul_seconds;
    if (rul == null) return "N/A";
    if (rul >= 600) return "> 10 min";
    if (rul <= 0) return "FAILURE";
    const band =
        prediction.rul_low != null && prediction.rul_high != null
            ? ` (${formatDuration(prediction.rul_low)} – ${formatDuration(prediction.rul_high)})`
            : "";
    return `~${formatDuration(rul)}${band}`;
}

function formatEta(seconds: number | null): string | null {
    if (seconds == null) return null;
    if (seconds <= 0) return "failure threshold reached";
    if (seconds >= 600) return "> 10 min to failure";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return m > 0 ? `~${m} min ${s} s to failure` : `~${s} s to failure`;
}

function AdvisoryPanel({ advisory }: { advisory: AdvisoryData | null }) {
    const mono = { fontFamily: "'JetBrains Mono', monospace" };

    if (!advisory) {
        return (
            <div className="mb-6 px-4 py-2 text-xs" style={{ ...mono, border: "1px solid #2a2a2a", color: "#7fe0a0" }}>
                MAINTENANCE ADVISORY: none active (engine nominal)
            </div>
        );
    }

    const color = ADVISORY_COLOR[advisory.level];
    const eta = formatEta(advisory.eta_seconds);

    return (
        <div className="mb-6" style={{ border: `1px solid ${color}`, background: "rgba(255,255,255,0.02)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3" style={{ borderBottom: `1px solid ${color}55`, ...mono }}>
                <span className="text-sm font-bold" style={{ color }}>
                    ⚠ {advisory.level} — {advisory.title}
                </span>
                {eta && <span className="text-sm font-semibold" style={{ color }}>{eta}</span>}
            </div>
            <div className="grid md:grid-cols-3 gap-4 px-4 py-3 text-sm">
                <div>
                    <div className="text-xs mb-1.5 font-semibold" style={{ ...mono, color: "#c0c0c0", letterSpacing: 1 }}>EVIDENCE</div>
                    <ul className="flex flex-col gap-1" style={{ color: "#d8d8d8" }}>
                        {advisory.evidence.map((line) => <li key={line}>{line}</li>)}
                    </ul>
                </div>
                <div>
                    <div className="text-xs mb-1.5 font-semibold" style={{ ...mono, color, letterSpacing: 1 }}>DO NOW</div>
                    <ul className="flex flex-col gap-1" style={{ color: "#fff" }}>
                        {advisory.do_now.map((line) => <li key={line}>{line}</li>)}
                    </ul>
                </div>
                <div>
                    <div className="text-xs mb-1.5 font-semibold" style={{ ...mono, color: "#c0c0c0", letterSpacing: 1 }}>MAINTENANCE AFTER LANDING</div>
                    <ul className="flex flex-col gap-1" style={{ color: "#d8d8d8" }}>
                        {advisory.maintenance.map((line) => <li key={line}>{line}</li>)}
                    </ul>
                </div>
            </div>
        </div>
    );
}



function RadialHealth({ value }: { value: number | null }) {
    const r = 42;
    const c = 2 * Math.PI * r;
    const offset = c - ((value ?? 0) / 100) * c;
    return (
        <svg width="100" height="100" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r={r} stroke="#2a2a2a" strokeWidth="6" fill="none" />
            <circle
                cx="50" cy="50" r={r} stroke="#ffffff" strokeWidth="6" fill="none"
                strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
                transform="rotate(-90 50 50)"
            />
            <text x="50" y="47" textAnchor="middle" fontSize="20" fontWeight="600" fill="#fff" fontFamily="'Space Grotesk', sans-serif">
                {value == null ? "--" : `${value}%`}
            </text>
            <text x="50" y="63" textAnchor="middle" fontSize="8" fill="#888" fontFamily="'JetBrains Mono', monospace">
                HEALTH
            </text>
        </svg>
    );
}

export default function HudSection({
    engineData,
}: {
    engineData: ReturnType<typeof useEngineData>;
}) {
    const [simulationStatus, setSimulationStatus] = useState<
        "stopped" | "starting" | "running" | "stopping"
    >("stopped");

    const [selectedProfile, setSelectedProfile] = useState(
        MISSION_PROFILES[0].id
    );

    useEffect(() => {
    const checkSimulationStatus = async () => {
        try {
            const result = await getSimulationStatus(
                engineData.selectedEngine
            );

            setSimulationStatus(
                result.status === "running"
                    ? "running"
                    : "stopped"
            );

            // Follow the run that is already in progress.
            if (result.status === "running") {
                if (result.profile) setSelectedProfile(result.profile);
                if (result.mission_id) {
                    engineData.setSelectedMission(result.mission_id);
                }
            }
        } catch {
            setSimulationStatus("stopped");
        }
    };

    checkSimulationStatus();
}, [engineData.selectedEngine]);

    const [isInjectingFault, setIsInjectingFault] = useState(false);
    const [controlStatus, setControlStatus] = useState<string | null>(null);

    const handleStartSimulation = async () => {
        setSimulationStatus("starting");
        setControlStatus(null);

        try {
            const result = await startSimulation(
                engineData.selectedEngine,
                selectedProfile
            );

            // Every run is a new mission; show its telemetry.
            if (result.mission_id) {
                engineData.setSelectedMission(result.mission_id);
            }

            engineData.setSimulationRunning(true);
            setSimulationStatus("running");
            setControlStatus(
                result.fault_id === 0
                    ? "SIMULATION STARTED — ENGINE HEALTHY"
                    : "SIMULATION STARTED"
            );
        } catch (err: any) {
            setSimulationStatus("stopped");
            setControlStatus(`START FAILED: ${err.message}`);
        }
    };

    const handleStopSimulation = async () => {
        setSimulationStatus("stopping");
        setControlStatus(null);

        try {
            await stopSimulation(engineData.selectedEngine);

            engineData.resetTelemetry();

            setSimulationStatus("stopped");
            setControlStatus("SIMULATION STOPPED");
        } catch (err: any) {
            setSimulationStatus("running");
            setControlStatus(`STOP FAILED: ${err.message}`);
        }
    };

    const handleInjectFault = async (faultId: number) => {
        setIsInjectingFault(true);
        setControlStatus(null);

        try {
            await injectFault(
                engineData.selectedEngine,
                faultId
            );

            const label =
                faultId === 0
                    ? "HEALTHY"
                    : `FAULT ${faultId}`;

            setControlStatus(`FAULT COMMAND SENT — ${label}`);
        } catch (err: any) {
            setControlStatus(`FAULT FAILED: ${err.message}`);
        } finally {
            setIsInjectingFault(false);
        }
    };

    const noData = !engineData.hasData;

    const subsystems = [
        { name: "THERMAL", score: engineData.health.thermal, status: engineData.health.thermal < 80 ? "warn" : "ok" },
        { name: "COMBUSTION", score: engineData.health.combustion, status: engineData.health.combustion < 80 ? "warn" : "ok" },
        { name: "LUBRICATION", score: engineData.health.lubrication, status: engineData.health.lubrication < 80 ? "warn" : "ok" },
        { name: "MECHANICAL", score: engineData.health.mechanical, status: engineData.health.mechanical < 80 ? "warn" : "ok" },
        { name: "ELECTRICAL", score: engineData.health.electrical, status: (engineData.health.electrical ?? 100) < 80 ? "warn" : "ok" },
        { name: "INJECTION", score: engineData.health.injection, status: (engineData.health.injection ?? 100) < 80 ? "warn" : "ok" },
        // Instrumentation health; not part of the overall score.
        { name: "SENSOR", score: engineData.health.sensor, status: (engineData.health.sensor ?? 100) < 80 ? "warn" : "ok" },
    ];

    const statusColor: Record<string, string> = { ok: "#7fe0a0", warn: "#e8c34a", critical: "#e8543f" };

    return (
        <section style={{ background: "#0b0b0b", color: "#d8d8d8", fontFamily: "'Space Grotesk', sans-serif" }} className="relative overflow-hidden">
            <div
                className="pointer-events-none absolute inset-0 opacity-[0.5]"
                style={{ backgroundImage: "linear-gradient(to bottom, #1a1a1a 1px, transparent 1px)", backgroundSize: "100% 64px" }}
            />

            <div className="relative z-10 px-6 md:px-10 py-16 md:py-20">
                <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
                    <div>
                        <h2 className="mt-2 font-bold" style={{ fontSize: "clamp(2rem, 4vw, 3rem)", color: "#fff" }}>
                            TEST AND FAULT CONTROL
                        </h2>
                    </div>

                </div>

                <div
                    className="mb-6 p-5"
                    style={{
                        border: "1px solid #3a3a3a",
                        background: "#0e0e0e",
                    }}
                >
                    <div
                        className="flex items-center justify-between mb-4"
                        style={{
                            fontFamily: "'JetBrains Mono', monospace",
                        }}
                    >
                        <span className="text-base font-bold" style={{ color: "#fff" }}>
                            SIMULATION CONTROL
                        </span>

                        <span
                            className="text-sm font-semibold"
                            style={{
                                color:
                                    simulationStatus === "running"
                                        ? "#7fe0a0"
                                        : simulationStatus === "starting" ||
                                        simulationStatus === "stopping"
                                        ? "#e8c34a"
                                        : "#bbb",
                            }}
                        >
                            ● {simulationStatus.toUpperCase()}
                        </span>
                    </div>

                    <div className="mb-3">
                        <label
                            htmlFor="mission-profile"
                            className="block text-xs mb-1.5 font-semibold"
                            style={{
                                color: "#c0c0c0",
                                fontFamily: "'JetBrains Mono', monospace",
                                letterSpacing: 1,
                            }}
                        >
                            MISSION PROFILE
                        </label>
                        <select
                            id="mission-profile"
                            value={selectedProfile}
                            onChange={(e) => setSelectedProfile(e.target.value)}
                            disabled={simulationStatus !== "stopped"}
                            className="px-3 py-2 text-sm"
                            style={{
                                background: "#151515",
                                color: "#fff",
                                border: "1px solid #666",
                                fontFamily: "'JetBrains Mono', monospace",
                                cursor:
                                    simulationStatus !== "stopped"
                                        ? "not-allowed"
                                        : "pointer",
                            }}
                        >
                            {MISSION_PROFILES.map((profile) => (
                                <option key={profile.id} value={profile.id}>
                                    {profile.label} — {profile.description}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        <button
                            onClick={handleStartSimulation}
                            disabled={
                                simulationStatus === "running" ||
                                simulationStatus === "starting"
                            }
                            className="px-6 py-3 text-sm font-bold transition"
                            style={{
                                background:
                                    simulationStatus === "running"
                                        ? "#222"
                                        : "#C6FF3D",
                                color:
                                    simulationStatus === "running"
                                        ? "#555"
                                        : "#050505",
                                cursor:
                                    simulationStatus === "running"
                                        ? "not-allowed"
                                        : "pointer",
                            }}
                        >
                            {simulationStatus === "starting"
                                ? "STARTING..."
                                : "START SIMULATION"}
                        </button>

                        <button
                            onClick={handleStopSimulation}
                            disabled={
                                simulationStatus === "stopped" ||
                                simulationStatus === "stopping"
                            }
                            className="px-6 py-3 text-sm font-bold transition"
                            style={{
                                border: "1px solid #666",
                                background: "#151515",
                                color: "#fff",
                                cursor:
                                    simulationStatus === "stopped"
                                        ? "not-allowed"
                                        : "pointer",
                            }}
                        >
                            {simulationStatus === "stopping"
                                ? "STOPPING..."
                                : "STOP SIMULATION"}
                        </button>
                    </div>

                    {controlStatus && (
                        <div
                            className="mt-4 text-sm font-semibold"
                            style={{
                                color: "#7fd4ff",
                                fontFamily: "'JetBrains Mono', monospace",
                            }}
                        >
                            {controlStatus}
                        </div>
                    )}
                </div>

                <div
                    className="mb-6 p-5"
                    style={{ border: "1px solid #5a1a1a", background: "#0e0808" }}
                >
                    <div
                        className="flex items-center justify-between mb-4"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                        <span className="text-sm font-bold flex items-center gap-2" style={{ color: "#e8543f" }}>
                            <AlertTriangle size={14} />
                            FAULT INJECTION
                        </span>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {/* Clear / Healthy */}
                        <button
                            onClick={() => handleInjectFault(0)}
                            disabled={isInjectingFault || simulationStatus !== "running"}
                            className="px-4 py-2.5 text-sm font-bold transition hover:brightness-110"
                            title="Inject fault_id=0 — clears any active fault, sets engine to healthy"
                            style={{
                                border: "1.5px solid #358452",
                                background: "rgba(34,197,94,0.22)",
                                color: "#ffffff",
                                cursor: isInjectingFault || simulationStatus !== "running" ? "not-allowed" : "pointer",
                                fontFamily: "'JetBrains Mono', monospace",
                                letterSpacing: "0.02em",
                            }}
                        >
                             HEALTHY
                        </button>

                        {/* Fault buttons */}
                        {[
                            { id: 1, label: "MISFIRE",          desc: "Reduced combustion performance" },
                            { id: 2, label: "OVERHEATING",       desc: "Elevated CHT, EGT and oil temperature" },
                            { id: 3, label: "OIL PRESSURE",      desc: "Progressive lubrication pressure loss" },
                            { id: 4, label: "FUEL STARVATION",   desc: "Reduced fuel supply causing engine power loss" },
                            { id: 5, label: "INJECTOR",          desc: "Fouled injector delivers less fuel than the ECU commands" },
                            { id: 6, label: "COOLING",           desc: "Degraded cylinder cooling: CHT creeps up while EGT stays normal" },
                            { id: 7, label: "SENSOR DRIFT",      desc: "CHT thermocouple drifts high and reads erratically; engine itself is healthy" },
                            { id: 8, label: "COMBUSTION",        desc: "Combustion instability: cycle-to-cycle torque variation makes RPM rough" },
                            { id: 9, label: "VIBRATION",         desc: "Abnormal vibration from imbalance / bearing wear" },
                        ].map(({ id, label, desc }) => (
                            <button
                                key={id}
                                onClick={() => handleInjectFault(id)}
                                disabled={isInjectingFault || simulationStatus !== "running"}
                                title={desc}
                                className="px-4 py-2.5 text-sm font-bold transition hover:brightness-110"
                                style={{
                                    border: "1.5px solid #e8543f",
                                    background: "rgba(168, 59, 44, 0.22)",
                                    color: "#ffffff",
                                    cursor:
                                        isInjectingFault || simulationStatus !== "running"
                                            ? "not-allowed"
                                            : "pointer",
                                    fontFamily: "'JetBrains Mono', monospace",
                                    letterSpacing: "0.02em",
                                }}
                            >
                                {isInjectingFault ? "INJECTING…" : label}
                            </button>
                        ))}
                    </div>

                </div>


                {engineData.isWarmup && (
                    <div className="mb-6 px-4 py-2 text-xs rounded" style={{ background: "rgba(234,179,8,0.1)", border: "1px solid #eab308", color: "#eab308", fontFamily: "'JetBrains Mono', monospace" }}>
                        WARM-UP IN PROGRESS: Health &amp; prediction models calibrating until 60 samples accumulate.
                    </div>
                )}

                <AdvisoryPanel advisory={engineData.advisory} />

                <div className="grid md:grid-cols-5 gap-8">
                    <div className="md:col-span-2 flex flex-col gap-6">
                        <div style={{ border: "1px solid #3a3a3a", background: "#0e0e0e" }}>
                            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid #3a3a3a", fontFamily: "'JetBrains Mono', monospace" }}>
                                <span className="text-base font-bold" style={{ color: "#fff" }}>UNIT &mdash; {engineData.selectedEngine}</span>
                                <span className="text-sm font-semibold" style={{ color: noData ? "#888" : statusColor[engineData.operatingState === "NOMINAL" ? "ok" : "warn"] }}>
                                    {noData ? "NO DATA" : engineData.operatingState}
                                </span>
                            </div>

                            <div className="p-5 flex gap-4 items-center">
                        <RadialHealth value={noData ? null : Math.round(engineData.health.overall)} />

                                <div className="flex-1">
                                    <div
                                        className="font-bold text-base tracking-tight"
                                        style={{ color: "#fff" }}
                                    >
                                        {noData
                                            ? "NO DATA"
                                            : engineData.health.overall > 90
                                                ? "NOMINAL"
                                                : engineData.health.overall > 75
                                                    ? "GOOD"
                                                    : "DEGRADED"}
                                    </div>

                                    <div
                                        className="text-sm mt-2"
                                        style={{
                                            color: "#c0c0c0",
                                            fontFamily: "'JetBrains Mono', monospace",
                                        }}
                                    >
                                        FAULT:{" "}
                                        <span style={{ color: "#fff" }}>
                                            {noData ? "--" : engineData.prediction.fault ?? "NONE DETECTED"}
                                        </span>
                                    </div>

                                    <div
                                        className="text-sm mt-1"
                                        style={{
                                            color: "#c0c0c0",
                                            fontFamily: "'JetBrains Mono', monospace",
                                        }}
                                        title="Power per unit of fuel; 100 = warmed-up healthy engine"
                                    >
                                        EFFICIENCY:{" "}
                                        <span style={{ color: engineData.efficiency != null && engineData.efficiency < 90 ? "#e8c34a" : "#fff" }}>
                                            {engineData.efficiency == null ? "--" : `${Math.round(engineData.efficiency)} / 100`}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* ML MODEL OUTPUT */}
                            <div
                                className="mx-5 mb-4 p-4"
                                style={{
                                    border: "1px solid #303030",
                                    background: "#111111",
                                }}
                            >
                                <div
                                    className="text-xs font-bold mb-3"
                                    style={{
                                        color: "#888",
                                        fontFamily: "'JetBrains Mono', monospace",
                                        letterSpacing: "0.08em",
                                    }}
                                >
                                    PREDICTIVE MODEL OUTPUT
                                </div>

                                <div
                                    className="grid grid-cols-2 gap-x-6 gap-y-3 text-xs"
                                    style={{
                                        fontFamily: "'JetBrains Mono', monospace",
                                    }}
                                >
                                    <div>
                                        <div style={{ color: "#777" }}>
                                            ANOMALY SCORE
                                        </div>

                                        <div
                                            className="mt-1 font-bold text-sm"
                                            style={{
                                                color: engineData.prediction.is_anomaly
                                                    ? "#e8c34a"
                                                    : "#7fe0a0",
                                            }}
                                        >
                                            {noData ? "--" : engineData.prediction.anomaly_score.toFixed(2)}
                                        </div>
                                    </div>

                                    <div>
                                        <div style={{ color: "#777" }}>
                                            STATUS
                                        </div>

                                        <div
                                            className="mt-1 font-bold text-sm"
                                            style={{
                                                color: engineData.prediction.is_anomaly
                                                    ? "#e8543f"
                                                    : "#7fe0a0",
                                            }}
                                        >
                                            {noData
                                                ? "--"
                                                : engineData.prediction.is_anomaly
                                                    ? "ANOMALOUS"
                                                    : "NORMAL"}
                                        </div>
                                    </div>

                                    <div>
                                        <div style={{ color: "#777" }}>
                                            FAULT
                                        </div>

                                        <div
                                            className="mt-1 font-bold text-sm"
                                            style={{ color: "#fff" }}
                                        >
                                            {noData ? "--" : engineData.prediction.fault ?? "NONE"}
                                        </div>
                                    </div>

                                    <div>
                                        <div style={{ color: "#777" }}>
                                            CONFIDENCE
                                        </div>

                                        <div
                                            className="mt-1 font-bold text-sm"
                                            style={{ color: "#fff" }}
                                        >
                                            {noData ? "--" : `${(engineData.prediction.confidence * 100).toFixed(2)}%`}
                                        </div>
                                    </div>

                                    <div className="col-span-2">
                                        <div style={{ color: "#777" }}>
                                            ESTIMATED RUL
                                        </div>

                                        <div
                                            className="mt-1 font-bold text-base"
                                            style={{ color: "#C6FF3D" }}
                                        >
                                            {noData ? "--" : formatRul(engineData.prediction)}
                                        </div>
                                    </div>

                                    <div className="col-span-2">
                                        <div style={{ color: "#777" }}>
                                            SIGNALS BEHIND THE CALL
                                        </div>

                                        <div
                                            className="mt-1 text-sm"
                                            style={{ color: "#fff" }}
                                        >
                                            {noData || !engineData.prediction.top_features?.length
                                                ? "--"
                                                : engineData.prediction.top_features
                                                    .map(([name]) => SIGNAL_LABEL[name] ?? name)
                                                    .join(", ")}
                                        </div>

                                        {!noData && engineData.prediction.source && (
                                            <div className="mt-2 text-xs" style={{ color: "#666" }}>
                                                {describeSource(engineData.prediction.source)}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                        </div>

                        <div style={{ border: "1px solid #3a3a3a", background: "#0e0e0e" }} className="p-4">
                            <div className="mb-3 flex items-center justify-between" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                                <span className="text-base font-bold" style={{ color: "#fff" }}>SUBSYSTEM HEALTH SCORES</span>
                            </div>
                            <div className="flex flex-col gap-3">
                                {subsystems.map((sub, idx) => (
                                    <div key={idx} className="text-sm">
                                        <div className="flex justify-between items-center mb-1.5" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                                            <span style={{ color: "#e0e0e0", fontWeight: 600 }}>{sub.name}</span>
                                            <span style={{ color: !noData && sub.status === "warn" ? "#e8c34a" : "#fff", fontWeight: 700 }}>{noData || sub.score == null ? "--" : `${sub.score}%`}</span>
                                        </div>
                                        <div className="w-full h-2 rounded-full" style={{ background: "#333" }}>
                                            <div
                                                className="h-full rounded-full"
                                                style={{
                                                    width: noData || sub.score == null ? "0%" : `${sub.score}%`,
                                                    background: sub.status === "warn" ? "#e8c34a" : "#7fe0a0",
                                                }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="md:col-span-3 flex flex-col gap-6">
                        

                        <div style={{ border: "1px solid #3a3a3a", background: "#0e0e0e" }} className="p-4">
                            <div className="flex items-center justify-between mb-3" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                                <span className="text-base font-bold" style={{ color: "#fff" }}>ACTIVE ALERTS</span>
                                <span className="text-sm font-semibold" style={{ color: "#e8c34a" }}>{engineData.alerts.length} DETECTED</span>
                            </div>
                            <div
                                className="flex flex-col gap-2 overflow-y-auto"
                                style={{
                                    maxHeight: "468px",
                                    scrollbarWidth: "thin",
                                }}
                            >
                                {engineData.alerts.map((al, idx) => {
                                    const isEngine = al.source === "operating_state";
                                    return (
                                        <div
                                            key={idx}
                                            className="flex items-start justify-between gap-3 p-3 rounded"
                                            style={{
                                                border: isEngine ? "1px solid rgba(232,84,63,0.4)" : "1px solid rgba(127,212,255,0.4)",
                                                background: isEngine ? "rgba(232,84,63,0.08)" : "rgba(127,212,255,0.08)",
                                            }}
                                        >
                                            <div className="flex items-start gap-2.5">
                                                {isEngine ? (
                                                    <AlertTriangle size={16} className="shrink-0 mt-0.5" color="#e8543f" />
                                                ) : (
                                                    <Wifi size={16} className="shrink-0 mt-0.5" color="#7fd4ff" />
                                                )}
                                                <div>
                                                    <div className="font-bold text-sm" style={{ color: isEngine ? "#fff" : "#7fd4ff" }}>
                                                        {al.message}
                                                    </div>
                                                </div>
                                            </div>
                                            <span className="text-xs shrink-0" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#b0b0b0" }}>
                                                {al.timestamp}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div
                className="relative z-10 px-6 md:px-10 py-6 flex items-center justify-center text-sm"
                style={{
                    borderTop: "1px solid #3a3a3a",
                    fontFamily: "'JetBrains Mono', monospace",
                    color: "#c0c0c0"
                }}
            >
                <span>SKOPEO • TEAM RAMBHAROSE</span>
            </div>
        </section>
    );
}

import React, { useState, useEffect } from "react";
import {
    Zap, Radio, Activity, GitBranch, ArrowUpRight, Circle,
    Gauge, Thermometer, Droplet, Wind, BatteryCharging, Timer,
    ArrowUp, ArrowDown, Minus, AlertTriangle, Wrench,
} from "lucide-react";

const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
`;

function useClock() {
    const [t, setT] = useState(new Date());
    useEffect(() => {
        const id = setInterval(() => setT(new Date()), 1000);
        return () => clearInterval(id);
    }, []);
    return t;
}
const pad = (n) => n.toString().padStart(2, "0");

// ---------- Section 1: Cyber-Brutalist hero (twin platform) ----------

function SensorMeshGraphic() {
    const nodes = [
        { x: 60, y: 40 }, { x: 200, y: 20 }, { x: 260, y: 110 },
        { x: 120, y: 140 }, { x: 30, y: 170 }, { x: 220, y: 200 },
        { x: 150, y: 70 },
    ];
    const edges = [[0, 6], [6, 1], [6, 2], [6, 3], [3, 4], [2, 5], [3, 5]];
    return (
        <svg viewBox="0 0 300 230" className="w-full h-full">
            {edges.map(([a, b], i) => (
                <line key={i} x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y} stroke="#2a2a2a" strokeWidth="1" />
            ))}
            {edges.map(([a, b], i) => (
                <circle key={"p" + i} r="3" fill="#C6FF3D">
                    <animateMotion
                        dur={`${2.2 + (i % 3) * 0.6}s`}
                        repeatCount="indefinite"
                        path={`M${nodes[a].x},${nodes[a].y} L${nodes[b].x},${nodes[b].y}`}
                    />
                </circle>
            ))}
            {nodes.map((n, i) => (
                <circle key={i} cx={n.x} cy={n.y} r={i === 6 ? 6 : 4} fill="#0d0d0d" stroke="#C6FF3D" strokeWidth="1.2" />
            ))}
        </svg>
    );
}

function CyberBrutalSection() {
    const time = useClock();
    const [glitch, setGlitch] = useState(false);

    const stats = [
        { label: "MODEL SYNC RATE", value: "50Hz" },
        { label: "INFERENCE LATENCY", value: "22ms" },
        { label: "TWIN FIDELITY", value: "98.4%" },
    ];

    const features = [
        { icon: Activity, title: "LIVE SENSOR FUSION", body: "Ten channels of engine telemetry streamed into the twin in real time, no batching." },
        { icon: GitBranch, title: "PHYSICS-INFORMED MODEL", body: "The twin runs a physical engine model alongside the data, not just a black box." },
        { icon: AlertTriangle, title: "FAULT DETECTION", body: "Deviations between twin and reality are scored and classified as they emerge." },
        { icon: Timer, title: "RUL PREDICTION", body: "Remaining useful life is re-estimated continuously as new fault evidence arrives." },
    ];

    return (
        <section style={{ background: "#050505", color: "#e8e8e8", fontFamily: "'Space Grotesk', sans-serif" }} className="relative overflow-hidden">
            <div
                className="pointer-events-none absolute inset-0 opacity-[0.35]"
                style={{
                    backgroundImage: "linear-gradient(to right, #161616 1px, transparent 1px), linear-gradient(to bottom, #161616 1px, transparent 1px)",
                    backgroundSize: "42px 42px",
                }}
            />

            <div className="relative z-10 flex items-center justify-between px-6 md:px-10 py-5 border-b" style={{ borderColor: "#1c1c1c" }}>
                <div className="flex items-center gap-2">
                    <span style={{ background: "#C6FF3D" }} className="w-3 h-3 inline-block" />
                    <span className="tracking-tight font-bold text-lg">ENGINE_TWIN</span>
                </div>
                <div className="hidden md:flex items-center gap-8 text-sm" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#9a9a9a" }}>
                    <span className="hover:text-white cursor-pointer">overview</span>
                    <span className="hover:text-white cursor-pointer">telemetry</span>
                    <span className="hover:text-white cursor-pointer">diagnostics</span>
                    <span className="hover:text-white cursor-pointer">docs</span>
                </div>
                <div className="flex items-center gap-4">
                    <span className="hidden sm:inline text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                        {pad(time.getHours())}:{pad(time.getMinutes())}:{pad(time.getSeconds())} UTC
                    </span>
                    <button style={{ background: "#C6FF3D", color: "#050505" }} className="text-sm font-semibold px-4 py-2 flex items-center gap-1.5 hover:brightness-95 transition">
                        OPEN DASHBOARD <ArrowUpRight size={14} />
                    </button>
                </div>
            </div>

            <div className="relative z-10 grid md:grid-cols-2 gap-10 px-6 md:px-10 py-16 md:py-24 items-center">
                <div>
                    <div className="inline-block text-xs mb-6 px-2 py-1" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#C6FF3D", border: "1px solid #2a3a10" }}>
                        /01 &nbsp; DIGITAL TWIN PLATFORM
                    </div>
                    <h1
                        onMouseEnter={() => setGlitch(true)}
                        onMouseLeave={() => setGlitch(false)}
                        className="font-bold leading-[0.95] mb-6"
                        style={{ fontSize: "clamp(2.5rem, 6vw, 4.5rem)" }}
                    >
                        <span style={{ position: "relative", display: "inline-block" }}>
                            KNOW THE FAILURE
                            {glitch && (
                                <span aria-hidden style={{ position: "absolute", left: 2, top: 0, color: "#ff2d55", clipPath: "inset(0 0 55% 0)", opacity: 0.7 }}>
                                    KNOW THE FAILURE
                                </span>
                            )}
                        </span>
                        <br />
                        BEFORE IT HAPPENS.
                    </h1>
                    <p className="max-w-md mb-8" style={{ color: "#9a9a9a", fontSize: "1rem", lineHeight: 1.6 }}>
                        A live physics-informed twin of the engine, fed by ten sensor channels,
                        scoring faults and re-estimating remaining useful life every cycle.
                    </p>
                    <div className="flex items-center gap-4">
                        <button style={{ background: "#C6FF3D", color: "#050505" }} className="font-semibold px-5 py-3 text-sm">
                            VIEW LIVE TWIN
                        </button>
                        <button style={{ border: "1px solid #2c2c2c" }} className="px-5 py-3 text-sm text-gray-300 hover:border-gray-500 transition">
                            MODEL DETAILS
                        </button>
                    </div>
                </div>

                <div className="relative" style={{ border: "1px solid #1c1c1c", background: "#0a0a0a" }}>
                    <div className="flex items-center justify-between px-4 py-2 text-xs" style={{ borderBottom: "1px solid #1c1c1c", fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                        <span>&gt;SENSOR_MESH</span>
                        <Radio size={12} color="#C6FF3D" />
                    </div>
                    <div className="h-64 md:h-72">
                        <SensorMeshGraphic />
                    </div>
                    <div className="px-4 py-2 text-xs flex justify-between" style={{ borderTop: "1px solid #1c1c1c", fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                        <span>CHANNELS: 10</span>
                        <span>NODE: TWIN_CORE</span>
                    </div>
                </div>
            </div>

            <div className="relative z-10 px-6 md:px-10 py-14" style={{ borderTop: "1px solid #1c1c1c" }}>
                <div className="text-xs mb-8" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                    /02 &nbsp; HOW THE TWIN WORKS
                </div>
                <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-px" style={{ background: "#1c1c1c" }}>
                    {features.map((f, i) => (
                        <div key={i} style={{ background: "#050505" }} className="p-6">
                            <f.icon size={18} color="#C6FF3D" />
                            <div className="mt-4 font-semibold text-sm tracking-tight">{f.title}</div>
                            <p className="mt-2 text-sm" style={{ color: "#8a8a8a", lineHeight: 1.5 }}>{f.body}</p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="relative z-10 px-6 md:px-10 py-6 flex flex-wrap gap-8 items-center justify-between" style={{ borderTop: "1px solid #1c1c1c", fontFamily: "'JetBrains Mono', monospace" }}>
                <div className="flex items-center gap-2 text-xs">
                    <Circle size={8} fill="#C6FF3D" color="#C6FF3D" />
                    <span style={{ color: "#C6FF3D" }}>TWIN SYNCED &mdash; LIVE</span>
                </div>
                <div className="flex flex-wrap gap-8">
                    {stats.map((s, i) => (
                        <div key={i} className="text-xs">
                            <div style={{ color: "#6f6f6f" }}>{s.label}</div>
                            <div style={{ color: "#e8e8e8" }} className="mt-1">{s.value}</div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

// ---------- Section 2: retro HUD — Engine Status + telemetry ----------

function HexTile({ filled }) {
    return (
        <svg width="18" height="20" viewBox="0 0 18 20">
            <polygon points="9,0 18,5 18,15 9,20 0,15 0,5" fill={filled ? "#ffffff" : "none"} stroke="#666" strokeWidth="1" />
        </svg>
    );
}

function TrendArrow({ trend }) {
    if (trend === "up") return <ArrowUp size={12} color="#e8543f" />;
    if (trend === "down") return <ArrowDown size={12} color="#7fd4ff" />;
    return <Minus size={12} color="#777" />;
}

function RadialHealth({ value }) {
    const r = 42;
    const c = 2 * Math.PI * r;
    const offset = c - (value / 100) * c;
    return (
        <svg width="100" height="100" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r={r} stroke="#2a2a2a" strokeWidth="6" fill="none" />
            <circle
                cx="50" cy="50" r={r} stroke="#ffffff" strokeWidth="6" fill="none"
                strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
                transform="rotate(-90 50 50)"
            />
            <text x="50" y="47" textAnchor="middle" fontSize="20" fontWeight="600" fill="#fff" fontFamily="'Space Grotesk', sans-serif">
                {value}%
            </text>
            <text x="50" y="63" textAnchor="middle" fontSize="8" fill="#888" fontFamily="'JetBrains Mono', monospace">
                HEALTH
            </text>
        </svg>
    );
}

function HudSection() {
    const time = useClock();

    const engine = {
        health: 82,
        healthLabel: "GOOD",
        status: "WARNING",
        fault: "Misfire detected",
        confidence: 94,
        rul: "18.4 hrs",
        trend: "DECLINING",
        subsystem: "COMBUSTION",
        action: "Inspect injector / combustion system",
    };

    const indicators = [
        { label: "EGT", trend: "up" },
        { label: "VIBRATION", trend: "up" },
        { label: "RPM STABILITY", trend: "down" },
    ];

    const sensors = [
        { icon: Gauge, label: "RPM", value: "2,340", unit: "rpm", status: "warn", trend: "down" },
        { icon: Thermometer, label: "CHT", value: "218", unit: "°C", status: "ok", trend: "flat" },
        { icon: Thermometer, label: "EGT", value: "812", unit: "°C", status: "critical", trend: "up" },
        { icon: Droplet, label: "OIL PRESSURE", value: "54", unit: "psi", status: "ok", trend: "flat" },
        { icon: Thermometer, label: "OIL TEMP", value: "97", unit: "°C", status: "ok", trend: "up" },
        { icon: Droplet, label: "FUEL FLOW", value: "11.2", unit: "gal/hr", status: "ok", trend: "flat" },
        { icon: Activity, label: "VIBRATION", value: "4.8", unit: "mm/s", status: "warn", trend: "up" },
        { icon: BatteryCharging, label: "BATTERY V", value: "24.6", unit: "V", status: "ok", trend: "flat" },
        { icon: Zap, label: "ALTERNATOR I", value: "38", unit: "A", status: "ok", trend: "flat" },
        { icon: Timer, label: "INJECTION TIMING", value: "18.5", unit: "°BTDC", status: "warn", trend: "down" },
    ];

    const statusColor = { ok: "#7fe0a0", warn: "#e8c34a", critical: "#e8543f" };

    return (
        <section style={{ background: "#0b0b0b", color: "#d8d8d8", fontFamily: "'Space Grotesk', sans-serif" }} className="relative overflow-hidden">
            <div
                className="pointer-events-none absolute inset-0 opacity-[0.5]"
                style={{ backgroundImage: "linear-gradient(to bottom, #1a1a1a 1px, transparent 1px)", backgroundSize: "100% 64px" }}
            />

            <div className="relative z-10 px-6 md:px-10 py-16 md:py-20">
                <div className="flex items-center justify-between mb-12 flex-wrap gap-4">
                    <div>
                        <div className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#777" }}>
                            /03 &nbsp; ENGINE STATUS MESSAGE
                        </div>
                        <h2 className="mt-2 font-semibold" style={{ fontSize: "clamp(1.8rem, 3.5vw, 2.6rem)" }}>
                            Live diagnostic readout
                        </h2>
                    </div>
                    <div className="flex gap-1">
                        {[...Array(9)].map((_, i) => <HexTile key={i} filled={i === 4} />)}
                    </div>
                </div>

                <div className="grid md:grid-cols-5 gap-8">
                    {/* engine status dossier card */}
                    <div className="md:col-span-2" style={{ border: "1px solid #2a2a2a" }}>
                        <div className="flex items-center justify-between px-4 py-3 text-xs" style={{ borderBottom: "1px solid #2a2a2a", fontFamily: "'JetBrains Mono', monospace", color: "#888" }}>
                            <span>UNIT — ENG_01</span>
                            <span style={{ color: statusColor.warn }}>{engine.status}</span>
                        </div>

                        <div className="p-5 flex gap-4 items-center">
                            <RadialHealth value={engine.health} />
                            <div className="flex-1">
                                <div className="font-semibold tracking-tight">{engine.healthLabel}</div>
                                <div className="text-xs" style={{ color: "#888", fontFamily: "'JetBrains Mono', monospace" }}>
                                    TREND: {engine.trend}
                                </div>
                                <div className="mt-3 flex items-center gap-2 text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                                    <AlertTriangle size={12} color={statusColor.critical} />
                                    <span style={{ color: "#fff" }}>{engine.fault}</span>
                                </div>
                                <div className="text-xs mt-1" style={{ color: "#888", fontFamily: "'JetBrains Mono', monospace" }}>
                                    CONFIDENCE {engine.confidence}%
                                </div>
                            </div>
                        </div>

                        <div className="px-5 pb-4 grid grid-cols-2 gap-y-2 text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#999" }}>
                            <span>EST. RUL</span><span style={{ color: "#fff" }}>{engine.rul}</span>
                            <span>SUBSYSTEM</span><span style={{ color: "#fff" }}>{engine.subsystem}</span>
                        </div>

                        <div className="px-5 pb-4">
                            <div className="text-xs mb-1.5" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#777" }}>KEY INDICATORS</div>
                            <div className="flex flex-wrap gap-3">
                                {indicators.map((ind, i) => (
                                    <span key={i} className="flex items-center gap-1 text-xs px-2 py-1" style={{ border: "1px solid #2a2a2a", fontFamily: "'JetBrains Mono', monospace" }}>
                                        {ind.label} <TrendArrow trend={ind.trend} />
                                    </span>
                                ))}
                            </div>
                        </div>

                        <div className="px-5 pb-4 flex items-start gap-2 text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#ccc" }}>
                            <Wrench size={12} className="mt-0.5 shrink-0" color="#C6FF3D" />
                            <span>{engine.action}</span>
                        </div>

                        <div className="px-4 py-3 text-xs flex justify-between" style={{ borderTop: "1px solid #2a2a2a", fontFamily: "'JetBrains Mono', monospace", color: "#666" }}>
                            <span>LAST UPDATED</span>
                            <span>{pad(time.getHours())}:{pad(time.getMinutes())}:{pad(time.getSeconds())}</span>
                        </div>
                    </div>

                    {/* telemetry grid */}
                    <div className="md:col-span-3" style={{ border: "1px solid #2a2a2a" }}>
                        <div className="px-4 py-3 text-xs flex items-center gap-2" style={{ borderBottom: "1px solid #2a2a2a", fontFamily: "'JetBrains Mono', monospace", color: "#888" }}>
                            <Activity size={12} /> TELEMETRY_CHANNELS
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-2">
                            {sensors.map((s, i) => (
                                <div
                                    key={i}
                                    className="flex items-center gap-3 px-4 py-3"
                                    style={{
                                        borderBottom: i < sensors.length - 2 ? "1px solid #1e1e1e" : "none",
                                        borderRight: i % 2 === 0 ? "1px solid #1e1e1e" : "none",
                                    }}
                                >
                                    <s.icon size={14} color="#888" className="shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#888" }}>{s.label}</div>
                                        <div className="text-sm font-semibold" style={{ color: "#fff" }}>
                                            {s.value} <span className="text-xs font-normal" style={{ color: "#888" }}>{s.unit}</span>
                                        </div>
                                    </div>
                                    <div className="flex flex-col items-center gap-1 shrink-0">
                                        <TrendArrow trend={s.trend} />
                                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor[s.status] }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="px-4 py-3 flex items-center justify-between text-xs" style={{ borderTop: "1px solid #2a2a2a", fontFamily: "'JetBrains Mono', monospace", color: "#666" }}>
                            <span className="flex items-center gap-1.5"><GitBranch size={12} /> 10 channels, 50Hz sample rate</span>
                            <span>SCN_ENG01</span>
                        </div>
                    </div>
                </div>
            </div>

            <div className="relative z-10 px-6 md:px-10 py-6 flex items-center justify-between text-xs" style={{ borderTop: "1px solid #1e1e1e", fontFamily: "'JetBrains Mono', monospace", color: "#666" }}>
                <span>ENGINE_TWIN &copy; 2026</span>
                <span>MODEL: PHYSICS-INFORMED HYBRID</span>
            </div>
        </section>
    );
}

export default function EngineTwinLanding() {
    return (
        <div>
            <style>{FONTS}</style>
            <CyberBrutalSection />
            <HudSection />
        </div>
    );
}

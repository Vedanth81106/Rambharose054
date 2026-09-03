import { useState, useEffect, useRef } from "react";
import type { LucideIcon } from "lucide-react";
import DroneOverviewSection from "./DroneOverview";
import {
    Radio, Activity, GitBranch, ArrowUpRight, Circle,
    Gauge, Thermometer, Droplet, Timer,
    ArrowUp, ArrowDown, Minus, AlertTriangle, Wrench,
} from "lucide-react";

const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

@keyframes cyberPulse {
    0%, 100% { opacity: 0.4; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.5); }
}
@keyframes cyberScan {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}
@keyframes cyberRing {
    0% { opacity: 0.8; transform: scale(0.3); }
    100% { opacity: 0; transform: scale(2.5); }
}
`;

function useClock(): Date {
    const [t, setT] = useState<Date>(new Date());
    useEffect(() => {
        const id = setInterval(() => setT(new Date()), 1000);
        return () => clearInterval(id);
    }, []);
    return t;
}
const pad = (n: number): string => n.toString().padStart(2, "0");

function DroneRadarGraphic() {
    const [tick, setTick] = useState(0);
    useEffect(() => {
        const id = setInterval(() => setTick(t => t + 1), 40);
        return () => clearInterval(id);
    }, []);

    const phase = tick * 0.04;
    const cx = 240, cy = 160;

    const droneX = cx + Math.cos(phase * 0.6) * 100;
    const droneY = cy + Math.sin(phase * 0.6) * 60;
    const droneHeading = Math.round(((Math.atan2(
        Math.cos(phase * 0.6) * 60,
        -Math.sin(phase * 0.6) * 100
    ) * 180) / Math.PI + 360) % 360);

    const altitude = Math.round(120 + Math.sin(phase * 0.3) * 25 + Math.sin(phase * 0.9) * 8);
    const speed = Math.round(14 + Math.sin(phase * 0.5) * 4);
    const battery = Math.round(87 - tick * 0.005);
    const battColor = battery > 60 ? "#C6FF3D" : battery > 30 ? "#e8c34a" : "#e8543f";

    const sweepAngle = (tick * 3) % 360;

    const waypoints = [
        { x: cx - 90, y: cy - 45, label: "WP1" },
        { x: cx + 80, y: cy - 55, label: "WP2" },
        { x: cx + 95, y: cy + 40, label: "WP3" },
        { x: cx - 85, y: cy + 50, label: "WP4" },
    ];

    const rotorAngle = tick * 15;

    return (
        <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
            <svg viewBox="0 0 480 320" style={{ width: "100%", height: "100%", display: "block", background: "#0a0a0a" }}>
                {Array.from({ length: 25 }, (_, i) => (
                    <line key={`vg${i}`} x1={i * 20} y1={0} x2={i * 20} y2={320} stroke="#141414" strokeWidth="0.5" />
                ))}
                {Array.from({ length: 17 }, (_, i) => (
                    <line key={`hg${i}`} x1={0} y1={i * 20} x2={480} y2={i * 20} stroke="#141414" strokeWidth="0.5" />
                ))}

                {[40, 80, 120].map((r, i) => (
                    <circle key={`ring${i}`} cx={cx} cy={cy} r={r} fill="none" stroke="#1a2a10" strokeWidth="0.8" />
                ))}
                <line x1={cx - 130} y1={cy} x2={cx + 130} y2={cy} stroke="#1a2a10" strokeWidth="0.5" />
                <line x1={cx} y1={cy - 130} x2={cx} y2={cy + 130} stroke="#1a2a10" strokeWidth="0.5" />

                <defs>
                    <linearGradient id="sweepGrad" gradientTransform={`rotate(${sweepAngle}, 0.5, 0.5)`}>
                        <stop offset="0%" stopColor="transparent" />
                        <stop offset="70%" stopColor="transparent" />
                        <stop offset="100%" stopColor="rgba(198,255,61,0.15)" />
                    </linearGradient>
                </defs>
                <line
                    x1={cx} y1={cy}
                    x2={cx + 130 * Math.cos((sweepAngle * Math.PI) / 180)}
                    y2={cy + 130 * Math.sin((sweepAngle * Math.PI) / 180)}
                    stroke="#C6FF3D" strokeWidth="1.5" opacity="0.4"
                />
                {[1, 2, 3, 4, 5].map(i => {
                    const a = ((sweepAngle - i * 8) * Math.PI) / 180;
                    return (
                        <line key={`sw${i}`} x1={cx} y1={cy}
                            x2={cx + 130 * Math.cos(a)} y2={cy + 130 * Math.sin(a)}
                            stroke="#C6FF3D" strokeWidth="1" opacity={0.08 * (6 - i)} />
                    );
                })}

                <ellipse cx={cx} cy={cy} rx={100} ry={60} fill="none"
                    stroke="#C6FF3D" strokeWidth="0.8" strokeDasharray="6 4" opacity="0.25" />

                {waypoints.map((wp, i) => {
                    const dist = Math.hypot(droneX - wp.x, droneY - wp.y);
                    const isNear = dist < 40;
                    return (
                        <g key={`wp${i}`}>
                            <rect x={wp.x - 6} y={wp.y - 6} width={12} height={12}
                                fill="none" stroke={isNear ? "#C6FF3D" : "#3b82f6"} strokeWidth="1"
                                transform={`rotate(45, ${wp.x}, ${wp.y})`} opacity={isNear ? 1 : 0.5} />
                            {isNear && (
                                <circle cx={wp.x} cy={wp.y} r={18} fill="none"
                                    stroke="#C6FF3D" strokeWidth="0.5" opacity={0.3 + Math.sin(phase * 4) * 0.3}>
                                    <animate attributeName="r" values="12;22;12" dur="1.5s" repeatCount="indefinite" />
                                    <animate attributeName="opacity" values="0.5;0.1;0.5" dur="1.5s" repeatCount="indefinite" />
                                </circle>
                            )}
                            <text x={wp.x} y={wp.y + 20} textAnchor="middle" fontSize="7"
                                fill={isNear ? "#C6FF3D" : "#555"} fontFamily="'JetBrains Mono', monospace">
                                {wp.label}
                            </text>
                        </g>
                    );
                })}

                <g transform={`translate(${droneX}, ${droneY})`}>
                    <circle cx={0} cy={0} r={28} fill="rgba(198,255,61,0.03)" stroke="#C6FF3D" strokeWidth="0.5" opacity="0.3" />

                    <line x1={-10} y1={-10} x2={10} y2={10} stroke="#888" strokeWidth="1.5" />
                    <line x1={10} y1={-10} x2={-10} y2={10} stroke="#888" strokeWidth="1.5" />

                    {[[-10, -10], [10, -10], [10, 10], [-10, 10]].map(([rx, ry], i) => (
                        <g key={`rotor${i}`} transform={`rotate(${rotorAngle + i * 90}, ${rx}, ${ry})`}>
                            <circle cx={rx} cy={ry} r={7} fill="none" stroke="#C6FF3D" strokeWidth="0.6" opacity="0.5" />
                            <line x1={rx - 6} y1={ry} x2={rx + 6} y2={ry} stroke="#C6FF3D" strokeWidth="0.8" opacity="0.7" />
                            <line x1={rx} y1={ry - 6} x2={rx} y2={ry + 6} stroke="#C6FF3D" strokeWidth="0.8" opacity="0.7" />
                        </g>
                    ))}

                    <circle cx={0} cy={0} r={4} fill="#222" stroke="#C6FF3D" strokeWidth="1" />
                    <circle cx={0} cy={0} r={1.5} fill="#C6FF3D" />

                    <line x1={0} y1={-4} x2={0} y2={-9} stroke="#e8543f" strokeWidth="1.5" strokeLinecap="round" />
                </g>

                {[1, 2, 3, 4, 5, 6, 7, 8].map(i => {
                    const tp = phase - i * 0.08;
                    const tx = cx + Math.cos(tp * 0.6) * 100;
                    const ty = cy + Math.sin(tp * 0.6) * 60;
                    return <circle key={`trail${i}`} cx={tx} cy={ty} r={1.2} fill="#C6FF3D" opacity={0.3 - i * 0.03} />;
                })}

                <rect x="12" y="50" width="28" height="220" fill="rgba(10,10,10,0.8)" stroke="#1e1e1e" strokeWidth="0.8" rx="2" />
                {Array.from({ length: 11 }, (_, i) => {
                    const val = 50 + i * 20;
                    const yp = 260 - i * 20;
                    return (
                        <g key={`at${i}`}>
                            <line x1="36" y1={yp} x2="40" y2={yp} stroke="#444" strokeWidth="0.8" />
                            <text x="34" y={yp + 3} textAnchor="end" fontSize="6" fill="#666" fontFamily="'JetBrains Mono', monospace">{val}</text>
                        </g>
                    );
                })}
                {(() => {
                    const altY = 260 - ((altitude - 50) / 200) * 200;
                    return (
                        <g>
                            <rect x="12" y={altY - 6} width="28" height="12" fill="#C6FF3D" rx="1" />
                            <text x="26" y={altY + 2} textAnchor="middle" fontSize="7" fill="#050505" fontWeight="bold" fontFamily="'JetBrains Mono', monospace">{altitude}</text>
                        </g>
                    );
                })()}
                <text x="26" y="44" textAnchor="middle" fontSize="6" fill="#777" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.5">ALT m</text>

                <rect x="170" y="8" width="140" height="18" fill="rgba(10,10,10,0.8)" stroke="#1e1e1e" strokeWidth="0.8" rx="2" />
                {[-60, -30, 0, 30, 60].map(offset => {
                    const hdg = ((droneHeading + offset) % 360 + 360) % 360;
                    const px = 240 + offset * 1.8;
                    const labels: Record<number, string> = { 0: "N", 90: "E", 180: "S", 270: "W" };
                    const isCardinal = labels[hdg] !== undefined;
                    return (
                        <g key={`hdg${offset}`}>
                            <line x1={px} y1={22} x2={px} y2={offset % 30 === 0 ? 26 : 24} stroke={isCardinal ? "#C6FF3D" : "#555"} strokeWidth="0.8" />
                            <text x={px} y={19} textAnchor="middle" fontSize={isCardinal ? "7" : "6"}
                                fill={isCardinal ? "#C6FF3D" : "#666"} fontFamily="'JetBrains Mono', monospace" fontWeight={isCardinal ? "bold" : "normal"}>
                                {isCardinal ? labels[hdg] : hdg}
                            </text>
                        </g>
                    );
                })}
                <polygon points="240,27 237,32 243,32" fill="#e8543f" />

                <rect x="370" y="250" width="100" height="60" fill="rgba(10,10,10,0.85)" stroke="#1e1e1e" strokeWidth="0.8" rx="2" />
                <text x="378" y="264" fontSize="7" fill="#777" fontFamily="'JetBrains Mono', monospace">SPD</text>
                <text x="462" y="264" textAnchor="end" fontSize="9" fill="#fff" fontFamily="'JetBrains Mono', monospace">{speed} m/s</text>
                <line x1="375" y1="268" x2="465" y2="268" stroke="#1e1e1e" strokeWidth="0.5" />
                <text x="378" y="280" fontSize="7" fill="#777" fontFamily="'JetBrains Mono', monospace">HDG</text>
                <text x="462" y="280" textAnchor="end" fontSize="9" fill="#fff" fontFamily="'JetBrains Mono', monospace">{droneHeading}°</text>
                <line x1="375" y1="284" x2="465" y2="284" stroke="#1e1e1e" strokeWidth="0.5" />
                <text x="378" y="296" fontSize="7" fill="#777" fontFamily="'JetBrains Mono', monospace">BAT</text>
                <text x="462" y="296" textAnchor="end" fontSize="9" fill={battColor} fontFamily="'JetBrains Mono', monospace">{battery}%</text>
                <rect x="375" y="300" width="90" height="3" fill="#1e1e1e" rx="1" />
                <rect x="375" y="300" width={Math.max(0, battery * 0.9)} height="3" fill={battColor} rx="1" />

                <rect x="12" y="282" width="80" height="28" fill="rgba(10,10,10,0.85)" stroke="#1e1e1e" strokeWidth="0.8" rx="2" />
                <circle cx="22" cy="296" r="3" fill="#C6FF3D" opacity={0.5 + Math.sin(phase * 3) * 0.5} />
                <text x="30" y="293" fontSize="7" fill="#C6FF3D" fontFamily="'JetBrains Mono', monospace">PATROL</text>
                <text x="30" y="303" fontSize="6" fill="#666" fontFamily="'JetBrains Mono', monospace">MODE: AUTO</text>

                <rect x="0" y={(tick * 2) % 320} width="480" height="2" fill="#C6FF3D" opacity="0.03" />
            </svg>

            <div style={{ position: "absolute", top: 8, left: 8, width: 16, height: 16, borderTop: "2px solid #C6FF3D", borderLeft: "2px solid #C6FF3D", pointerEvents: "none", zIndex: 10 }} />
            <div style={{ position: "absolute", top: 8, right: 8, width: 16, height: 16, borderTop: "2px solid #C6FF3D", borderRight: "2px solid #C6FF3D", pointerEvents: "none", zIndex: 10 }} />
            <div style={{ position: "absolute", bottom: 8, left: 8, width: 16, height: 16, borderBottom: "2px solid #C6FF3D", borderLeft: "2px solid #C6FF3D", pointerEvents: "none", zIndex: 10 }} />
            <div style={{ position: "absolute", bottom: 8, right: 8, width: 16, height: 16, borderBottom: "2px solid #C6FF3D", borderRight: "2px solid #C6FF3D", pointerEvents: "none", zIndex: 10 }} />
        </div>
    );
}

interface FeatureItem {
    icon: LucideIcon;
    title: string;
    body: string;
}

function CyberBrutalSection({ onViewTwin }: { onViewTwin: () => void }) {
    const time = useClock();
    const [glitch, setGlitch] = useState(false);

    const stats = [
        { label: "MODEL SYNC RATE", value: "50Hz" },
        { label: "INFERENCE LATENCY", value: "22ms" },
        { label: "TWIN FIDELITY", value: "98.4%" },
    ];

    const features: FeatureItem[] = [
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
                                <span aria-hidden="true" style={{ position: "absolute", left: 2, top: 0, color: "#ff2d55", clipPath: "inset(0 0 55% 0)", opacity: 0.7 }}>
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
                        <button
                            onClick={onViewTwin}
                            style={{ background: "#C6FF3D", color: "#050505", cursor: "pointer" }}
                            className="font-semibold px-5 py-3 text-sm hover:brightness-110 transition"
                        >
                            VIEW LIVE TWIN
                        </button>
                        <button style={{ border: "1px solid #2c2c2c" }} className="px-5 py-3 text-sm text-gray-300 hover:border-gray-500 transition">
                            MODEL DETAILS
                        </button>
                    </div>
                </div>

                <div className="relative" style={{ border: "1px solid #1c1c1c", background: "#0a0a0a" }}>
                    <div className="flex items-center justify-between px-4 py-2 text-xs" style={{ borderBottom: "1px solid #1c1c1c", fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                        <span className="flex items-center gap-1.5"><Radio size={11} />&gt;DRONE_RADAR</span>
                        <Radio size={12} color="#C6FF3D" />
                    </div>
                    <div className="h-64 md:h-80">
                        <DroneRadarGraphic />
                    </div>
                    <div className="px-4 py-2 text-xs flex justify-between" style={{ borderTop: "1px solid #1c1c1c", fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                        <span>MODE: PATROL</span>
                        <span>NODE: UAV_CORE</span>
                    </div>
                </div>
            </div>

            <div className="relative z-10 px-6 md:px-10 py-14" style={{ borderTop: "1px solid #1c1c1c" }}>
                <div className="text-xs mb-8" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                    /02 &nbsp; HOW THE TWIN WORKS
                </div>
                <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-px" style={{ background: "#1c1c1c" }}>
                    {features.map((f, i) => {
                        const Icon = f.icon;
                        return (
                            <div key={i} style={{ background: "#050505" }} className="p-6">
                                <Icon size={18} color="#C6FF3D" />
                                <div className="mt-4 font-semibold text-sm tracking-tight">{f.title}</div>
                                <p className="mt-2 text-sm" style={{ color: "#8a8a8a", lineHeight: 1.5 }}>{f.body}</p>
                            </div>
                        );
                    })}
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

function HexTile({ filled }: { filled: boolean }) {
    return (
        <svg width="18" height="20" viewBox="0 0 18 20">
            <polygon points="9,0 18,5 18,15 9,20 0,15 0,5" fill={filled ? "#ffffff" : "none"} stroke="#666" strokeWidth="1" />
        </svg>
    );
}

function TrendArrow({ trend }: { trend: string }) {
    if (trend === "up") return <ArrowUp size={12} color="#e8543f" />;
    if (trend === "down") return <ArrowDown size={12} color="#7fd4ff" />;
    return <Minus size={12} color="#777" />;
}

function RadialHealth({ value }: { value: number }) {
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

interface SensorItem {
    icon: LucideIcon;
    label: string;
    value: string;
    unit: string;
    status: "ok" | "warn" | "critical";
    trend: string;
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

    const sensors: SensorItem[] = [
        { icon: Gauge, label: "RPM", value: "2,340", unit: "rpm", status: "warn", trend: "down" },
        { icon: Thermometer, label: "CHT", value: "218", unit: "°C", status: "ok", trend: "flat" },
        { icon: Thermometer, label: "EGT", value: "812", unit: "°C", status: "critical", trend: "up" },
        { icon: Droplet, label: "OIL PRESSURE", value: "54", unit: "psi", status: "ok", trend: "flat" },
        { icon: Thermometer, label: "OIL TEMP", value: "97", unit: "°C", status: "ok", trend: "up" },
        { icon: Droplet, label: "FUEL FLOW", value: "11.2", unit: "gal/hr", status: "ok", trend: "flat" },
        { icon: Activity, label: "VIBRATION", value: "4.8", unit: "mm/s", status: "warn", trend: "up" },
    ];

    const statusColor: Record<string, string> = { ok: "#7fe0a0", warn: "#e8c34a", critical: "#e8543f" };

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

                    <div className="md:col-span-3" style={{ border: "1px solid #2a2a2a" }}>
                        <div className="px-4 py-3 text-xs flex items-center gap-2" style={{ borderBottom: "1px solid #2a2a2a", fontFamily: "'JetBrains Mono', monospace", color: "#888" }}>
                            <Activity size={12} /> TELEMETRY_CHANNELS
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-2">
                            {sensors.map((s, i) => {
                                const SensorIcon = s.icon;
                                return (
                                    <div
                                        key={i}
                                        className="flex items-center gap-3 px-4 py-3"
                                        style={{
                                            borderBottom: i < sensors.length - 2 ? "1px solid #1e1e1e" : "none",
                                            borderRight: i % 2 === 0 ? "1px solid #1e1e1e" : "none",
                                        }}
                                    >
                                        <SensorIcon size={14} color="#888" className="shrink-0" />
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
                                );
                            })}
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
    const droneRef = useRef<HTMLDivElement>(null);

    const handleViewTwin = () => {
        droneRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    return (
        <div>
            <style>{FONTS}</style>
            <CyberBrutalSection onViewTwin={handleViewTwin} />
            <div ref={droneRef}>
                <DroneOverviewSection />
            </div>
            <HudSection />
        </div>
    );
}

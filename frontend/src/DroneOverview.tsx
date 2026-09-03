import { useState, useEffect, useRef, useCallback } from "react";
import { Layers, Monitor, Lock, Zap, RotateCcw, RotateCw, Move3d } from "lucide-react";

interface GaugeProps {
    value: number;
    max: number;
    label: string;
    unit: string;
    majorTicks: number;
    minorPerMajor: number;
    redZone?: number;
}

function AnalogGauge({ value, max, label, unit, majorTicks, minorPerMajor, redZone }: GaugeProps) {
    const S = 200, cx = 100, cy = 100, r = 78;
    const startDeg = -135, sweepDeg = 270;

    const polar = (deg: number, rad: number) => ({
        x: cx + rad * Math.sin((deg * Math.PI) / 180),
        y: cy - rad * Math.cos((deg * Math.PI) / 180),
    });

    const needleAngle = startDeg + (Math.min(value, max) / max) * sweepDeg;
    const ticks: JSX.Element[] = [];

    for (let i = 0; i <= majorTicks; i++) {
        const a = startDeg + (i / majorTicks) * sweepDeg;
        const tv = Math.round((i / majorTicks) * max);
        const red = redZone !== undefined && tv >= redZone;
        const o = polar(a, r), inn = polar(a, r - 12), lp = polar(a, r - 23);

        ticks.push(<line key={`M${i}`} x1={inn.x} y1={inn.y} x2={o.x} y2={o.y} stroke={red ? "#e8543f" : "#999"} strokeWidth="2" />);
        ticks.push(
            <text key={`L${i}`} x={lp.x} y={lp.y} textAnchor="middle" dominantBaseline="middle"
                fontSize="8" fill={red ? "#e8543f" : "#bbb"} fontFamily="'JetBrains Mono', monospace">{tv}</text>
        );
        if (i < majorTicks) {
            for (let j = 1; j < minorPerMajor; j++) {
                const ma = startDeg + ((i + j / minorPerMajor) / majorTicks) * sweepDeg;
                const mo = polar(ma, r), mi = polar(ma, r - 6);
                ticks.push(<line key={`m${i}_${j}`} x1={mi.x} y1={mi.y} x2={mo.x} y2={mo.y} stroke="#444" strokeWidth="1" />);
            }
        }
    }

    const tip = polar(needleAngle, r - 18);
    const tail = polar(needleAngle + 180, 10);

    return (
        <svg viewBox={`0 0 ${S} ${S + 24}`} className="w-full h-full">
            <circle cx={cx} cy={cy} r={r + 6} stroke="#2a2a2a" strokeWidth="2" fill="none" />
            <circle cx={cx} cy={cy} r={r} stroke="#1a1a1a" strokeWidth="1" fill="#0d0d0d" />
            {ticks}
            <line x1={tail.x} y1={tail.y} x2={tip.x} y2={tip.y} stroke="#e8543f" strokeWidth="2.5" strokeLinecap="round"
                style={{ transition: "all 0.3s ease-out" }} />
            <circle cx={cx} cy={cy} r="6" fill="#333" stroke="#555" strokeWidth="1.5" />
            <text x={cx} y={cy + 32} textAnchor="middle" fontSize="18" fontWeight="600" fill="#fff"
                fontFamily="'Space Grotesk', sans-serif">{value}</text>
            <text x={cx + 24} y={cy + 32} textAnchor="start" fontSize="8" fill="#888"
                fontFamily="'JetBrains Mono', monospace">{unit}</text>
            <text x={cx} y={S + 14} textAnchor="middle" fontSize="9" fill="#777" letterSpacing="2"
                fontFamily="'JetBrains Mono', monospace">{label}</text>
        </svg>
    );
}

function ShiftLightBar({ activeCount }: { activeCount: number }) {
    const segments = 24;
    return (
        <div className="flex gap-[2px] items-center">
            {Array.from({ length: segments }, (_, i) => {
                const pct = i / segments;
                let color = "#1a3a1a";
                if (i < activeCount) {
                    if (pct < 0.4) color = "#22c55e";
                    else if (pct < 0.7) color = "#eab308";
                    else color = "#ef4444";
                }
                return <div key={i} style={{ background: color, width: 14, height: 8, borderRadius: 1 }} />;
            })}
        </div>
    );
}

function PistonGraphic({ phase }: { phase: number }) {
    const py = 35 + Math.sin(phase) * 20;
    return (
        <svg viewBox="0 0 100 130" className="w-full h-full">
            <rect x="25" y="10" width="50" height="100" fill="none" stroke="#555" strokeWidth="1.5" rx="2" />
            <rect x="22" y="5" width="56" height="8" fill="none" stroke="#666" strokeWidth="1.5" rx="1" />
            <line x1="40" y1="5" x2="40" y2="0" stroke="#555" strokeWidth="1" />
            <line x1="60" y1="5" x2="60" y2="0" stroke="#555" strokeWidth="1" />
            <rect x="28" y={py} width="44" height="14" fill="#3a3a3a" stroke="#888" strokeWidth="1" rx="2" />
            <line x1="30" y1={py + 3} x2="70" y2={py + 3} stroke="#666" strokeWidth="0.8" />
            <line x1="30" y1={py + 6} x2="70" y2={py + 6} stroke="#666" strokeWidth="0.8" />
            <line x1="50" y1={py + 14} x2="50" y2={py + 45} stroke="#666" strokeWidth="3" strokeLinecap="round" />
            <circle cx="50" cy={py + 14} r="3" fill="#222" stroke="#888" strokeWidth="1" />
            <circle cx="50" cy="115" r="8" fill="none" stroke="#555" strokeWidth="1.5" />
            <circle cx="50" cy="115" r="2" fill="#888" />
        </svg>
    );
}

function ClutchPlateGraphic({ rotation }: { rotation: number }) {
    const cx = 60, cy = 60, outerR = 45, innerR = 18;
    const slots = 12;
    return (
        <svg viewBox="0 0 120 120" className="w-full h-full">
            <g transform={`rotate(${rotation}, ${cx}, ${cy})`}>
                <circle cx={cx} cy={cy} r={outerR} fill="none" stroke="#666" strokeWidth="2" />
                <circle cx={cx} cy={cy} r={outerR - 5} fill="none" stroke="#444" strokeWidth="1" />
                <circle cx={cx} cy={cy} r={innerR} fill="none" stroke="#666" strokeWidth="2" />
                <circle cx={cx} cy={cy} r={innerR - 4} fill="none" stroke="#555" strokeWidth="1" />
                {Array.from({ length: 6 }, (_, i) => {
                    const a = (i * 60 * Math.PI) / 180;
                    return <line key={i} x1={cx + innerR * Math.cos(a)} y1={cy + innerR * Math.sin(a)}
                        x2={cx + (outerR - 6) * Math.cos(a)} y2={cy + (outerR - 6) * Math.sin(a)}
                        stroke="#555" strokeWidth="1" />;
                })}
                {Array.from({ length: slots }, (_, i) => {
                    const a = (i * 30 * Math.PI) / 180;
                    const dr = (outerR + innerR) / 2;
                    return <circle key={`d${i}`} cx={cx + dr * Math.cos(a)} cy={cy + dr * Math.sin(a)}
                        r="2.5" fill="none" stroke="#555" strokeWidth="0.8" />;
                })}
                {Array.from({ length: 4 }, (_, i) => {
                    const a = ((i * 90 + 45) * Math.PI) / 180;
                    return <circle key={`b${i}`} cx={cx + (innerR + 6) * Math.cos(a)} cy={cy + (innerR + 6) * Math.sin(a)}
                        r="2" fill="#333" stroke="#666" strokeWidth="0.8" />;
                })}
            </g>
        </svg>
    );
}

function EngineTopFace() {
    return (
        <svg viewBox="0 0 260 160" style={{ width: "100%", height: "100%", display: "block" }}>
            <rect width="260" height="160" fill="#151515" />
            <rect x="10" y="10" width="240" height="140" fill="#1a1a1a" stroke="#444" strokeWidth="1.5" rx="4" />
            <rect x="30" y="20" width="200" height="120" fill="none" stroke="#333" strokeWidth="1" rx="2" />
            {[0,1,2,3,4].map(i => (
                <g key={`tb${i}`}>
                    <circle cx={50+i*42} cy={50} r="14" fill="#0d0d0d" stroke="#C6FF3D" strokeWidth="0.8" opacity="0.7" />
                    <circle cx={50+i*42} cy={50} r="5" fill="none" stroke="#444" strokeWidth="0.5" />
                    <circle cx={50+i*42} cy={110} r="14" fill="#0d0d0d" stroke="#C6FF3D" strokeWidth="0.8" opacity="0.7" />
                    <circle cx={50+i*42} cy={110} r="5" fill="none" stroke="#444" strokeWidth="0.5" />
                </g>
            ))}
            {[0,1,2,3,4,5].map(i => (
                <circle key={`bolt${i}`} cx={35+i*40} cy={80} r="2.5" fill="#333" stroke="#555" strokeWidth="0.5" />
            ))}
            <text x="130" y="155" textAnchor="middle" fontSize="7" fill="#555" fontFamily="'JetBrains Mono', monospace">TOP VIEW — CYLINDER BORES</text>
        </svg>
    );
}

function EngineBottomFace() {
    return (
        <svg viewBox="0 0 260 160" style={{ width: "100%", height: "100%", display: "block" }}>
            <rect width="260" height="160" fill="#111" />
            <rect x="20" y="15" width="220" height="130" fill="#151515" stroke="#444" strokeWidth="1.5" rx="3" />
            {[0,1,2,3,4,5,6].map(i => (
                <line key={`r${i}`} x1="30" y1={25+i*18} x2="230" y2={25+i*18} stroke="#2a2a2a" strokeWidth="1" />
            ))}
            <circle cx="130" cy="80" r="8" fill="#222" stroke="#666" strokeWidth="1.5" />
            <circle cx="130" cy="80" r="3" fill="#333" />
            {[0,1,2,3,4,5,6,7,8,9].map(i => (
                <circle key={`sb${i}`} cx={35+i*20} cy={20} r="1.5" fill="#444" />
            ))}
            {[0,1,2,3,4,5,6,7,8,9].map(i => (
                <circle key={`sb2${i}`} cx={35+i*20} cy={140} r="1.5" fill="#444" />
            ))}
            <text x="130" y="155" textAnchor="middle" fontSize="7" fill="#555" fontFamily="'JetBrains Mono', monospace">BOTTOM VIEW — OIL PAN</text>
        </svg>
    );
}

function EngineFrontFace() {
    return (
        <svg viewBox="0 0 260 160" style={{ width: "100%", height: "100%", display: "block" }}>
            <rect width="260" height="160" fill="#131313" />
            <rect x="30" y="10" width="200" height="130" fill="#1a1a1a" stroke="#444" strokeWidth="1.5" rx="3" />
            <rect x="50" y="15" width="160" height="80" fill="#161616" stroke="#555" strokeWidth="1" rx="2" />
            <circle cx="100" cy="50" r="22" fill="none" stroke="#555" strokeWidth="1.5" />
            <circle cx="100" cy="50" r="8" fill="#222" stroke="#666" strokeWidth="1" />
            <circle cx="160" cy="50" r="22" fill="none" stroke="#555" strokeWidth="1.5" />
            <circle cx="160" cy="50" r="8" fill="#222" stroke="#666" strokeWidth="1" />
            <circle cx="130" cy="110" r="18" fill="none" stroke="#C6FF3D" strokeWidth="1" opacity="0.5" />
            <circle cx="130" cy="110" r="6" fill="#333" stroke="#666" strokeWidth="1" />
            <path d="M100,72 Q100,90 112,110" fill="none" stroke="#888" strokeWidth="1.5" />
            <path d="M160,72 Q160,90 148,110" fill="none" stroke="#888" strokeWidth="1.5" />
            <path d="M100,28 L160,28" fill="none" stroke="#888" strokeWidth="1.5" />
            <circle cx="80" cy="120" r="10" fill="#181818" stroke="#555" strokeWidth="1" />
            <circle cx="80" cy="120" r="3" fill="#3a6a8a" />
            <text x="130" y="155" textAnchor="middle" fontSize="7" fill="#555" fontFamily="'JetBrains Mono', monospace">FRONT VIEW — TIMING / PULLEYS</text>
        </svg>
    );
}

function EngineBackFace() {
    return (
        <svg viewBox="0 0 260 160" style={{ width: "100%", height: "100%", display: "block" }}>
            <rect width="260" height="160" fill="#131313" />
            <rect x="40" y="10" width="180" height="130" fill="#1a1a1a" stroke="#444" strokeWidth="1.5" rx="3" />
            <circle cx="130" cy="75" r="55" fill="none" stroke="#444" strokeWidth="1.5" />
            <circle cx="130" cy="75" r="48" fill="#151515" stroke="#333" strokeWidth="1" />
            <circle cx="130" cy="75" r="38" fill="none" stroke="#C6FF3D" strokeWidth="1" opacity="0.4" />
            <circle cx="130" cy="75" r="30" fill="#111" stroke="#555" strokeWidth="1" />
            {[0,1,2,3,4,5].map(i => {
                const a = (i * 60 * Math.PI) / 180;
                return <circle key={`fb${i}`} cx={130 + 24 * Math.cos(a)} cy={75 + 24 * Math.sin(a)} r="2.5" fill="#333" stroke="#555" strokeWidth="0.5" />;
            })}
            <circle cx="130" cy="75" r="8" fill="#222" stroke="#666" strokeWidth="1.5" />
            <circle cx="130" cy="75" r="3" fill="#444" />
            <circle cx="130" cy="75" r="5" fill="none" stroke="#777" strokeWidth="0.5" />
            <text x="130" y="155" textAnchor="middle" fontSize="7" fill="#555" fontFamily="'JetBrains Mono', monospace">REAR VIEW — FLYWHEEL</text>
        </svg>
    );
}

function EngineLeftFace() {
    return (
        <svg viewBox="0 0 160 160" style={{ width: "100%", height: "100%", display: "block" }}>
            <rect width="160" height="160" fill="#131313" />
            <rect x="10" y="10" width="140" height="110" fill="#1a1a1a" stroke="#444" strokeWidth="1.5" rx="3" />
            <line x1="10" y1="35" x2="150" y2="35" stroke="#555" strokeWidth="1" strokeDasharray="4 2" />
            {[0,1,2,3,4].map(i => (
                <g key={`ep${i}`}>
                    <rect x="145" y={15+i*20} width="10" height="12" fill="#111" stroke="#e8543f" strokeWidth="0.8" rx="1" opacity="0.6" />
                    <line x1="155" y1={21+i*20} x2="160" y2={21+i*20} stroke="#e8543f" strokeWidth="1" opacity="0.4" />
                </g>
            ))}
            <path d="M155,21 Q165,21 168,40 Q170,60 168,80 Q165,100 155,101" fill="none" stroke="#e8543f" strokeWidth="1.5" opacity="0.4" />
            <rect x="15" y="40" width="130" height="75" fill="none" stroke="#2a2a2a" strokeWidth="0.5" />
            <rect x="20" y="118" width="120" height="15" fill="#151515" stroke="#444" strokeWidth="1" rx="2" />
            <circle cx="40" cy="100" r="10" fill="#181818" stroke="#555" strokeWidth="1" />
            <circle cx="40" cy="100" r="3" fill="#333" />
            <text x="80" y="155" textAnchor="middle" fontSize="7" fill="#555" fontFamily="'JetBrains Mono', monospace">LEFT — EXHAUST SIDE</text>
        </svg>
    );
}

function EngineRightFace() {
    return (
        <svg viewBox="0 0 160 160" style={{ width: "100%", height: "100%", display: "block" }}>
            <rect width="160" height="160" fill="#131313" />
            <rect x="10" y="10" width="140" height="110" fill="#1a1a1a" stroke="#444" strokeWidth="1.5" rx="3" />
            <line x1="10" y1="35" x2="150" y2="35" stroke="#555" strokeWidth="1" strokeDasharray="4 2" />
            {[0,1,2,3,4].map(i => (
                <g key={`ir${i}`}>
                    <rect x="-5" y={15+i*20} width="18" height="10" fill="#111" stroke="#3b82f6" strokeWidth="0.8" rx="1" opacity="0.6" />
                    <line x1="-5" y1={20+i*20} x2="-10" y2={20+i*20} stroke="#3b82f6" strokeWidth="1" opacity="0.4" />
                </g>
            ))}
            <path d="M5,21 Q-5,21 -8,40 Q-10,60 -8,80 Q-5,100 5,101" fill="none" stroke="#3b82f6" strokeWidth="1.5" opacity="0.4" />
            <rect x="15" y="40" width="130" height="75" fill="none" stroke="#2a2a2a" strokeWidth="0.5" />
            <rect x="20" y="118" width="120" height="15" fill="#151515" stroke="#444" strokeWidth="1" rx="2" />
            <rect x="100" y="85" width="30" height="18" fill="#181818" stroke="#555" strokeWidth="1" rx="3" />
            <circle cx="115" cy="94" r="5" fill="#222" stroke="#666" strokeWidth="0.8" />
            <text x="80" y="155" textAnchor="middle" fontSize="7" fill="#555" fontFamily="'JetBrains Mono', monospace">RIGHT — INTAKE SIDE</text>
        </svg>
    );
}

function Engine360Viewer() {
    const containerRef = useRef<HTMLDivElement>(null);
    const [rotX, setRotX] = useState(-25);
    const [rotY, setRotY] = useState(35);
    const [isDragging, setIsDragging] = useState(false);
    const [autoRotate, setAutoRotate] = useState(true);
    const dragStart = useRef({ x: 0, y: 0, rotX: 0, rotY: 0 });

    useEffect(() => {
        if (!autoRotate || isDragging) return;
        const id = setInterval(() => {
            setRotY(prev => prev + 0.3);
        }, 30);
        return () => clearInterval(id);
    }, [autoRotate, isDragging]);

    const handlePointerDown = useCallback((e: React.PointerEvent) => {
        setIsDragging(true);
        setAutoRotate(false);
        dragStart.current = { x: e.clientX, y: e.clientY, rotX, rotY };
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
    }, [rotX, rotY]);

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
        if (!isDragging) return;
        const dx = e.clientX - dragStart.current.x;
        const dy = e.clientY - dragStart.current.y;
        setRotY(dragStart.current.rotY + dx * 0.5);
        setRotX(Math.max(-80, Math.min(80, dragStart.current.rotX - dy * 0.5)));
    }, [isDragging]);

    const handlePointerUp = useCallback(() => {
        setIsDragging(false);
    }, []);

    const resetView = () => {
        setRotX(-25);
        setRotY(35);
        setAutoRotate(true);
    };

    const normalizedY = ((rotY % 360) + 360) % 360;
    let faceLabel = "FRONT";
    if (normalizedY >= 45 && normalizedY < 135) faceLabel = "RIGHT";
    else if (normalizedY >= 135 && normalizedY < 225) faceLabel = "REAR";
    else if (normalizedY >= 225 && normalizedY < 315) faceLabel = "LEFT";

    const W = 260, H = 160, D = 160;
    const halfW = W / 2, halfH = H / 2, halfD = D / 2;

    return (
        <div
            ref={containerRef}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
            style={{
                width: "100%", height: "100%", position: "relative",
                cursor: isDragging ? "grabbing" : "grab",
                userSelect: "none", touchAction: "none",
                perspective: 800,
                display: "flex", alignItems: "center", justifyContent: "center",
            }}
        >
            <div style={{
                width: W, height: H, position: "relative",
                transformStyle: "preserve-3d",
                transform: `rotateX(${rotX}deg) rotateY(${rotY}deg)`,
                transition: isDragging ? "none" : "transform 0.05s linear",
            }}>
                <div style={{
                    position: "absolute", width: W, height: H,
                    transform: `translateZ(${halfD}px)`,
                    backfaceVisibility: "hidden",
                }}>
                    <EngineFrontFace />
                </div>
                <div style={{
                    position: "absolute", width: W, height: H,
                    transform: `translateZ(${-halfD}px) rotateY(180deg)`,
                    backfaceVisibility: "hidden",
                }}>
                    <EngineBackFace />
                </div>
                <div style={{
                    position: "absolute", width: D, height: H,
                    left: (W - D) / 2,
                    transform: `translateX(${-halfD}px) rotateY(-90deg)`,
                    transformOrigin: `${halfD}px ${halfH}px`,
                    backfaceVisibility: "hidden",
                }}>
                    <EngineLeftFace />
                </div>
                <div style={{
                    position: "absolute", width: D, height: H,
                    left: (W - D) / 2,
                    transform: `translateX(${halfD}px) rotateY(90deg)`,
                    transformOrigin: `${halfD}px ${halfH}px`,
                    backfaceVisibility: "hidden",
                }}>
                    <EngineRightFace />
                </div>
                <div style={{
                    position: "absolute", width: W, height: D,
                    top: (H - D) / 2,
                    transform: `translateY(${-halfD}px) rotateX(90deg)`,
                    transformOrigin: `${halfW}px ${halfD}px`,
                    backfaceVisibility: "hidden",
                }}>
                    <EngineTopFace />
                </div>
                <div style={{
                    position: "absolute", width: W, height: D,
                    top: (H - D) / 2,
                    transform: `translateY(${halfD}px) rotateX(-90deg)`,
                    transformOrigin: `${halfW}px ${halfD}px`,
                    backfaceVisibility: "hidden",
                }}>
                    <EngineBottomFace />
                </div>
            </div>

            <div style={{
                position: "absolute", bottom: 6, left: 8, zIndex: 10,
                fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: "#C6FF3D",
                background: "rgba(5,5,5,0.8)", padding: "3px 8px",
                border: "1px solid rgba(198,255,61,0.2)",
                display: "flex", alignItems: "center", gap: 6,
            }}>
                <Move3d size={10} />
                <span>X:{Math.round(rotX)}° Y:{Math.round(normalizedY)}°</span>
                <span style={{ color: "#888", marginLeft: 4 }}>|</span>
                <span style={{ color: "#fff" }}>{faceLabel}</span>
            </div>

            <div style={{
                position: "absolute", top: 6, right: 8, zIndex: 10,
                display: "flex", gap: 4,
            }}>
                <button
                    onClick={(e) => { e.stopPropagation(); setAutoRotate(!autoRotate); }}
                    style={{
                        background: autoRotate ? "rgba(198,255,61,0.15)" : "rgba(255,255,255,0.05)",
                        border: `1px solid ${autoRotate ? "rgba(198,255,61,0.4)" : "#333"}`,
                        color: autoRotate ? "#C6FF3D" : "#666",
                        padding: "3px 6px", cursor: "pointer", display: "flex", alignItems: "center", gap: 3,
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                    }}
                >
                    <RotateCw size={10} /> {autoRotate ? "AUTO" : "MANUAL"}
                </button>
                <button
                    onClick={(e) => { e.stopPropagation(); resetView(); }}
                    style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid #333",
                        color: "#888", padding: "3px 6px", cursor: "pointer",
                        display: "flex", alignItems: "center", gap: 3,
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                    }}
                >
                    <RotateCcw size={10} /> RESET
                </button>
            </div>

            <div style={{
                position: "absolute", bottom: 6, right: 8, zIndex: 10,
                fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: "#555",
            }}>
                DRAG TO ROTATE
            </div>
        </div>
    );
}

function RadiatorGraphic() {
    return (
        <svg viewBox="0 0 100 130" className="w-full h-full">
            <rect x="15" y="10" width="70" height="90" fill="none" stroke="#555" strokeWidth="1.5" rx="2" />
            <rect x="15" y="8" width="70" height="8" fill="#222" stroke="#555" strokeWidth="1" rx="1" />
            <rect x="15" y="94" width="70" height="8" fill="#222" stroke="#555" strokeWidth="1" rx="1" />
            {Array.from({ length: 12 }, (_, i) => (
                <line key={i} x1={22 + i * 5.3} y1="16" x2={22 + i * 5.3} y2="94" stroke="#444" strokeWidth="1.2" />
            ))}
            {Array.from({ length: 8 }, (_, i) => (
                <line key={`h${i}`} x1="18" y1={22 + i * 10} x2="82" y2={22 + i * 10} stroke="#333" strokeWidth="0.5" />
            ))}
            <rect x="30" y="2" width="8" height="8" fill="#222" stroke="#555" strokeWidth="0.8" rx="1" />
            <rect x="60" y="100" width="8" height="8" fill="#222" stroke="#555" strokeWidth="0.8" rx="1" />
            <circle cx="50" cy="120" r="6" fill="none" stroke="#555" strokeWidth="1" />
            {Array.from({ length: 4 }, (_, i) => {
                const a = (i * 90 * Math.PI) / 180;
                return <line key={`f${i}`} x1={50 + 3 * Math.cos(a)} y1={120 + 3 * Math.sin(a)}
                    x2={50 + 6 * Math.cos(a)} y2={120 + 6 * Math.sin(a)} stroke="#4a8ab5" strokeWidth="1.5" />;
            })}
        </svg>
    );
}

function TelemetryCell({ label, value, unit, color = "#fff", warn = false }: {
    label: string; value: string | number; unit: string; color?: string; warn?: boolean;
}) {
    return (
        <div className="px-3 py-2" style={{
            border: `1px solid ${warn ? "rgba(232,84,63,0.4)" : "#1a1a1a"}`,
            borderRadius: 6, background: warn ? "rgba(232,84,63,0.05)" : "#0a0a0a",
        }}>
            <div className="text-[9px] mb-1" style={{
                color: warn ? "#e8543f" : "#555",
                fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1,
            }}>{label}</div>
            <div className="flex items-baseline gap-1">
                <span className="text-base font-semibold" style={{ color, fontFamily: "'Space Grotesk', sans-serif" }}>{value}</span>
                <span className="text-[9px]" style={{ color: "#666", fontFamily: "'JetBrains Mono', monospace" }}>{unit}</span>
            </div>
        </div>
    );
}

export default function DroneOverviewSection() {
    const [tick, setTick] = useState(0);
    const [elapsedSec, setElapsedSec] = useState(0);

    useEffect(() => {
        const id = setInterval(() => setTick(t => t + 1), 60);
        return () => clearInterval(id);
    }, []);

    useEffect(() => {
        const id = setInterval(() => setElapsedSec(s => s + 1), 1000);
        return () => clearInterval(id);
    }, []);

    const phase = tick * 0.08;
    const idleRPM = 820 + Math.sin(phase * 0.4) * 40 + Math.sin(phase * 1.1) * 15;
    const rpm = Math.round(idleRPM);
    const shiftActive = Math.floor((rpm / 9000) * 24);

    const torque = (12.4 + Math.sin(phase * 0.3) * 1.8 + Math.sin(phase * 0.9) * 0.6).toFixed(1);
    const power = (0.18 + Math.sin(phase * 0.35) * 0.03).toFixed(2);
    const fuelFlow = (2.1 + Math.sin(phase * 0.25) * 0.4 + Math.sin(phase * 0.7) * 0.15).toFixed(1);
    const cht = Math.round(185 + Math.sin(phase * 0.15) * 12 + Math.sin(phase * 0.5) * 5);
    const egt = Math.round(620 + Math.sin(phase * 0.2) * 30 + Math.sin(phase * 0.6) * 10);
    const oilTemp = Math.round(95 + Math.sin(phase * 0.12) * 8);
    const oilPressure = (58 + Math.sin(phase * 0.18) * 6 + Math.sin(phase * 0.55) * 2).toFixed(0);
    const vibration = (0.12 + Math.sin(phase * 1.2) * 0.04 + Math.sin(phase * 2.3) * 0.02).toFixed(2);
    const altitude = Math.round(150 + Math.sin(phase * 0.05) * 5);
    const ambientTemp = (28 + Math.sin(phase * 0.02) * 2).toFixed(1);
    const throttle = (5 + Math.sin(phase * 0.3) * 3 + Math.sin(phase * 0.8) * 1).toFixed(0);
    const engineLoad = (8 + Math.sin(phase * 0.28) * 4 + Math.sin(phase * 0.7) * 2).toFixed(0);

    const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, "0");
    const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, "0");
    const secs = String(elapsedSec % 60).padStart(2, "0");
    const timeStr = `${hrs}:${mins}:${secs}`;

    const statusLights = [
        { label: "ENGINE", color: "#22c55e" },
        { label: "FUEL", color: "#22c55e" },
        { label: "OIL", color: "#22c55e" },
        { label: "TEMP", color: "#22c55e" },
        { label: "IDLE", color: "#3b82f6" },
    ];

    return (
        <section style={{ background: "#0a0a0a", fontFamily: "'Space Grotesk', sans-serif" }} className="relative overflow-hidden">
            <div className="relative z-10 px-6 md:px-10 py-14">
                <div className="text-xs mb-8" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#6f6f6f" }}>
                    /03 &nbsp; ENGINE SIMULATION DASHBOARD
                </div>

                <div style={{ overflow: "hidden", background: "#111" }}>
                    <div className="flex items-center justify-between px-3 py-2 flex-wrap gap-2" style={{ background: "#151515", borderBottom: "1px solid #222" }}>
                        <div className="flex items-center gap-1">
                            {[Layers, Monitor, Lock, Zap].map((Icon, i) => (
                                <button key={i} className="p-1.5 rounded hover:bg-white/5 transition" style={{ color: "#888" }}>
                                    <Icon size={14} />
                                </button>
                            ))}
                            <button className="ml-2 px-3 py-1 text-xs font-bold rounded"
                                style={{ background: "#ef4444", color: "#fff", fontSize: 10 }}>CRANK</button>
                        </div>
                        <div className="flex items-center gap-3">
                            {statusLights.map((s, i) => (
                                <div key={i} className="flex items-center gap-1">
                                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.color, boxShadow: s.color !== "#555" ? `0 0 6px ${s.color}` : "none" }} />
                                    <span className="text-[9px] hidden sm:inline" style={{ color: "#666", fontFamily: "'JetBrains Mono', monospace" }}>{s.label}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-center justify-between px-4 py-2 flex-wrap gap-2" style={{ background: "#0f0f0f", borderBottom: "1px solid #1e1e1e" }}>
                        <div className="text-[10px] flex items-center gap-4" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#777" }}>
                            <span>SHIFT LIGHT</span>
                        </div>
                        <ShiftLightBar activeCount={shiftActive} />
                        <div className="text-[10px] flex items-center gap-4" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#777" }}>
                            <span>RPM <span style={{ color: "#fff" }}>{rpm}</span></span>
                            <span>OPTIMAL <span style={{ color: "#C6FF3D" }}>9000</span></span>
                        </div>
                        <span className="text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#e8c34a" }}>STANDBY</span>
                    </div>

                    <div className="flex" style={{ minHeight: 480 }}>
                        <div className="flex-1 p-4" style={{ background: "#0d0d0d" }}>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 h-full" style={{ gridTemplateRows: "auto 1fr auto" }}>
                                <div className="flex items-center justify-center p-2" style={{ border: "1px solid #1a1a1a", borderRadius: 6, background: "#0a0a0a" }}>
                                    <div className="w-24 h-32">
                                        <PistonGraphic phase={phase * 3} />
                                    </div>
                                </div>
                                <div className="flex items-center justify-center p-2" style={{ border: "1px solid #1a1a1a", borderRadius: 6, background: "#0a0a0a" }}>
                                    <div className="w-28 h-28">
                                        <ClutchPlateGraphic rotation={tick * 0.3} />
                                    </div>
                                </div>
                                <div className="hidden md:flex items-center justify-center p-2" style={{ border: "1px solid #1a1a1a", borderRadius: 6, background: "#0a0a0a" }}>
                                    <div className="w-24 h-32">
                                        <RadiatorGraphic />
                                    </div>
                                </div>
                                <div className="col-span-2 md:col-span-3 flex items-center justify-center p-3"
                                    style={{ border: "1px solid #1a1a1a", borderRadius: 6, background: "#0a0a0a", position: "relative", overflow: "hidden" }}>
                                    <div style={{ width: "100%", height: 280 }}>
                                        <Engine360Viewer />
                                    </div>
                                </div>
                                <div className="col-span-2 md:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-2">
                                    <TelemetryCell label="TIME" value={timeStr} unit="" color="#3b82f6" />
                                    <TelemetryCell label="TORQUE" value={torque} unit="N·m" />
                                    <TelemetryCell label="POWER" value={power} unit="kW" />
                                    <TelemetryCell label="FUEL FLOW" value={fuelFlow} unit="L/h" color="#eab308" />
                                </div>
                                <div className="col-span-2 md:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-2">
                                    <TelemetryCell label="CHT" value={cht} unit="°C" warn={cht > 195} />
                                    <TelemetryCell label="EGT" value={egt} unit="°C" warn={egt > 650} />
                                    <TelemetryCell label="OIL TEMP" value={oilTemp} unit="°C" />
                                    <TelemetryCell label="OIL PRESSURE" value={oilPressure} unit="psi" color="#22c55e" />
                                </div>
                                <div className="col-span-2 md:col-span-3 grid grid-cols-2 md:grid-cols-3 gap-2">
                                    <TelemetryCell label="VIBRATION" value={vibration} unit="g" warn={parseFloat(vibration) > 0.15} />
                                    <TelemetryCell label="ALTITUDE" value={altitude} unit="m" color="#a78bfa" />
                                    <TelemetryCell label="AMBIENT TEMP" value={ambientTemp} unit="°C" />
                                </div>
                                <div className="col-span-2 md:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                                    <div className="px-3 py-2" style={{ border: "1px solid #1a1a1a", borderRadius: 6, background: "#0a0a0a" }}>
                                        <div className="text-[9px] mb-1 flex justify-between" style={{ color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>
                                            <span>THROTTLE</span>
                                            <span style={{ color: "#eab308" }}>{throttle}%</span>
                                        </div>
                                        <div className="w-full h-3 rounded" style={{ background: "#3a2a1a" }}>
                                            <div className="h-full rounded" style={{
                                                width: `${throttle}%`,
                                                background: "linear-gradient(90deg, #eab308, #ca8a04)",
                                                transition: "width 0.3s ease-out",
                                            }} />
                                        </div>
                                    </div>
                                    <div className="px-3 py-2" style={{ border: "1px solid #1a1a1a", borderRadius: 6, background: "#0a0a0a" }}>
                                        <div className="text-[9px] mb-1 flex justify-between" style={{ color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>
                                            <span>ENGINE LOAD</span>
                                            <span style={{ color: "#3b82f6" }}>{engineLoad}%</span>
                                        </div>
                                        <div className="w-full h-3 rounded" style={{ background: "#1a2a3a" }}>
                                            <div className="h-full rounded" style={{
                                                width: `${engineLoad}%`,
                                                background: "linear-gradient(90deg, #3b82f6, #2563eb)",
                                                transition: "width 0.3s ease-out",
                                            }} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="hidden lg:flex flex-col w-56 shrink-0" style={{ background: "#111", borderLeft: "1px solid #1e1e1e" }}>
                            <div className="px-2 pt-3">
                                <AnalogGauge value={rpm} max={12000} label="ENGINE SPEED" unit="rpm"
                                    majorTicks={12} minorPerMajor={5} redZone={9000} />
                            </div>
                            <div className="flex-1 px-3 py-3 flex flex-col gap-2 overflow-y-auto" style={{ borderTop: "1px solid #1e1e1e" }}>
                                <div className="text-[9px] font-bold mb-1" style={{ color: "#666", fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
                                    KEY PARAMETERS
                                </div>
                                {[
                                    { label: "RPM", val: rpm, unit: "rpm", col: "#fff" },
                                    { label: "TORQUE", val: torque, unit: "N·m", col: "#fff" },
                                    { label: "POWER", val: power, unit: "kW", col: "#fff" },
                                    { label: "FUEL FLOW", val: fuelFlow, unit: "L/h", col: "#eab308" },
                                    { label: "CHT", val: cht, unit: "°C", col: cht > 195 ? "#e8543f" : "#fff" },
                                    { label: "EGT", val: egt, unit: "°C", col: egt > 650 ? "#e8543f" : "#fff" },
                                    { label: "OIL TEMP", val: oilTemp, unit: "°C", col: "#fff" },
                                    { label: "OIL PRESS", val: oilPressure, unit: "psi", col: "#22c55e" },
                                    { label: "VIBRATION", val: vibration, unit: "g", col: parseFloat(vibration) > 0.15 ? "#e8543f" : "#fff" },
                                    { label: "ALTITUDE", val: altitude, unit: "m", col: "#a78bfa" },
                                    { label: "AMB TEMP", val: ambientTemp, unit: "°C", col: "#fff" },
                                    { label: "THROTTLE", val: `${throttle}%`, unit: "", col: "#eab308" },
                                    { label: "ENG LOAD", val: `${engineLoad}%`, unit: "", col: "#3b82f6" },
                                ].map((p, i) => (
                                    <div key={i} className="flex items-center justify-between py-1" style={{ borderBottom: "1px solid #1a1a1a" }}>
                                        <span className="text-[9px]" style={{ color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>{p.label}</span>
                                        <span className="text-[11px] font-semibold" style={{ color: p.col, fontFamily: "'Space Grotesk', sans-serif" }}>
                                            {p.val} <span className="text-[8px]" style={{ color: "#666" }}>{p.unit}</span>
                                        </span>
                                    </div>
                                ))}
                            </div>
                            <div className="px-3 py-3" style={{ borderTop: "1px solid #1e1e1e" }}>
                                <div className="flex items-center justify-between">
                                    <span className="text-[9px]" style={{ color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>ELAPSED</span>
                                    <span className="text-sm font-bold" style={{ color: "#3b82f6", fontFamily: "'JetBrains Mono', monospace" }}>{timeStr}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}

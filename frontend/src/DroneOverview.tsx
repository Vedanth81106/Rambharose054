import { useEffect, useState } from "react";
import type { AdvisoryData, TelemetryData } from "./types/api";
import { profileFromMissionId } from "./missionProfiles";
import Drone3DViewer from "./Drone3DViewer";

interface GaugeProps {
    value: number;
    max: number;
    label: string;
    unit: string;
    majorTicks: number;
    minorPerMajor: number;
    redZone?: number;
    lowerRedZone?: number;
    }

function AnalogGauge({
        value,
        max,
        label,
        unit,
        majorTicks,
        minorPerMajor,
        redZone,
        lowerRedZone,
    }: GaugeProps) {
        const S = 200, cx = 100, cy = 100, r = 78;
        const startDeg = -135, sweepDeg = 270;

        const polar = (deg: number, rad: number) => ({
            x: cx + rad * Math.sin((deg * Math.PI) / 180),
            y: cy - rad * Math.cos((deg * Math.PI) / 180),
        });

        const needleAngle =
            startDeg + (Math.min(value, max) / max) * sweepDeg;

        const ticks: JSX.Element[] = [];

        for (let i = 0; i <= majorTicks; i++) {
            const a = startDeg + (i / majorTicks) * sweepDeg;
            const tv = Math.round((i / majorTicks) * max);

            const red =
                (redZone !== undefined && tv >= redZone) ||
                (lowerRedZone !== undefined && tv <= lowerRedZone);

            const o = polar(a, r);
            const inn = polar(a, r - 12);
            const lp = polar(a, r - 23);

            ticks.push(
                <line
                    key={`M${i}`}
                    x1={inn.x}
                    y1={inn.y}
                    x2={o.x}
                    y2={o.y}
                    stroke={red ? "#e8543f" : "#999"}
                    strokeWidth="2"
                />
            );

            ticks.push(
                <text
                    key={`L${i}`}
                    x={lp.x}
                    y={lp.y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="8"
                    fill={red ? "#e8543f" : "#bbb"}
                    fontFamily="'JetBrains Mono', monospace"
                >
                    {tv}
                </text>
            );

            if (i < majorTicks) {
                for (let j = 1; j < minorPerMajor; j++) {
                    const tickValue =
                        ((i + j / minorPerMajor) / majorTicks) * max;

                    const ma =
                        startDeg +
                        ((i + j / minorPerMajor) / majorTicks) * sweepDeg;

                    const mo = polar(ma, r);
                    const mi = polar(ma, r - 6);

                    const minorRed =
                        (redZone !== undefined && tickValue >= redZone) ||
                        (lowerRedZone !== undefined &&
                            tickValue <= lowerRedZone);

                    ticks.push(
                        <line
                            key={`m${i}_${j}`}
                            x1={mi.x}
                            y1={mi.y}
                            x2={mo.x}
                            y2={mo.y}
                            stroke={minorRed ? "#e8543f" : "#444"}
                            strokeWidth="1"
                        />
                    );
                }
            }
        }

        const needle = polar(needleAngle, r - 18);

        return (
            <div
                style={{
                    width: 250,
                    height: 250,
                    position: "relative",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                }}
            >
                <svg
                    width={S}
                    height={S}
                    viewBox="0 0 200 200"
                    style={{ overflow: "visible" }}
                >
                    {/* Gauge ticks */}
                    {ticks}

                    {/* Needle */}
                    <line
                        x1={cx}
                        y1={cy}
                        x2={needle.x}
                        y2={needle.y}
                        stroke="#e8543f"
                        strokeWidth="2"
                        strokeLinecap="round"
                    />

                    {/* Center */}
                    <circle
                        cx={cx}
                        cy={cy}
                        r="5"
                        fill="#e8543f"
                    />

                    {/* Value */}
                    <text
                        x={cx}
                        y="145"
                        textAnchor="middle"
                        fill="#fff"
                        fontSize="18"
                        fontFamily="'JetBrains Mono', monospace"
                        fontWeight="bold"
                    >
                        {Math.round(value)}
                    </text>

                    {/* Unit */}
                    <text
                        x={cx}
                        y="158"
                        textAnchor="middle"
                        fill="#888"
                        fontSize="8"
                        fontFamily="'JetBrains Mono', monospace"
                    >
                        {unit}
                    </text>
                </svg>

                {/* Label */}
                <div
                    style={{
                        position: "absolute",
                        top: 8,
                        left: 0,
                        right: 0,
                        textAlign: "center",
                        color: "#bbb",
                        fontSize: 15,
                        fontFamily: "'JetBrains Mono', monospace",
                    }}
                >
                    {label}
                </div>
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

// Telemetry recorded before a signal existed arrives as null/undefined.
function formatOptional(value: number | null | undefined, digits: number): string {
    return value == null ? "--" : value.toFixed(digits);
}

function TelemetryCell({
        label,
        value,
        unit,
        color = "#fff",
    }: {
        label: string;
        value: string | number;
        unit: string;
        color?: string;
    }) {
    // Plain readouts: fixed cruise limits turned healthy hot-weather or
    // high-altitude readings red. Health judgement (per profile) lives in
    // the subsystem scores, the advisory and the models.
    return (
        <div
            className="px-4 py-3"
            style={{
                border: "1px solid #3a3a3a",
                borderRadius: 6,
                background: "#0a0a0a",
            }}
        >
            <div
                className="text-xs mb-1.5 font-semibold"
                style={{
                    color: "#c0c0c0",
                    fontFamily: "'JetBrains Mono', monospace",
                    letterSpacing: 1,
                }}
            >
                {label}
            </div>

            <div className="flex items-baseline gap-1.5">
                <span
                    className="text-lg font-semibold"
                    style={{
                        color,
                        fontFamily: "'Space Grotesk', sans-serif",
                    }}
                >
                    {value}
                </span>

                <span
                    className="text-xs"
                    style={{
                        color: "#b0b0b0",
                        fontFamily: "'JetBrains Mono', monospace",
                    }}
                >
                    {unit}
                </span>
            </div>
        </div>
    );
}

export default function DroneOverviewSection({ liveTelemetry, advisory }: { liveTelemetry?: TelemetryData; advisory?: AdvisoryData | null }) {
    const [tick, setTick] = useState(0);

    useEffect(() => {
        const id = setInterval(() => setTick(t => t + 1), 60);
        return () => clearInterval(id);
    }, []);

    const phase = tick * 0.08;
    const rpm = liveTelemetry?.rpm ?? 0;
    const torque = (liveTelemetry?.torque ?? 0).toFixed(1);
    const fuelFlow = (liveTelemetry?.fuel_flow ?? 0).toFixed(1);
    const cht = Math.round(liveTelemetry?.cht ?? 0);
    const egt = Math.round(liveTelemetry?.egt ?? 0);
    const oilTemp = Math.round(liveTelemetry?.oil_temperature ?? 0);
    const oilPressure = String(Math.round(liveTelemetry?.oil_pressure ?? 0));
    const vibration = (liveTelemetry?.vibration ?? 0).toFixed(2);
    // Flight conditions: the mission profile's inputs to the engine model.
    const throttle = Math.round((liveTelemetry?.throttle ?? 0) * 100);
    const engineLoad = Math.round((liveTelemetry?.engine_load ?? 0) * 100);
    const altitude = Math.round(liveTelemetry?.altitude ?? 0);
    const ambientTemp = (liveTelemetry?.ambient_temperature ?? 0).toFixed(1);
    const profile = profileFromMissionId(liveTelemetry?.mission_id);
    const batteryVoltage = liveTelemetry?.battery_voltage;
    const alternatorCurrent = liveTelemetry?.alternator_current;
    const injectionTiming = liveTelemetry?.injection_timing;
    const injectionDuration = liveTelemetry?.injection_duration;


    // Simulink simulation clock, the time base fault onset/progression uses.
    const simTime = liveTelemetry?.sim_time;
    let timeStr = "--:--:--";
    if (simTime != null) {
        const elapsedSec = Math.floor(simTime);
        const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, "0");
        const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, "0");
        const secs = String(elapsedSec % 60).padStart(2, "0");
        timeStr = `${hrs}:${mins}:${secs}`;
    }

    return (
        <section style={{ background: "#0a0a0a", fontFamily: "'Space Grotesk', sans-serif" }} className="relative overflow-hidden">
            <div className="relative z-10 px-6 md:px-10 py-14">
                <div className="text-sm mb-8 font-semibold" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#b0b0b0" }}>
                    &nbsp; ENGINE SIMULATION DASHBOARD
                </div>

                <div style={{ overflow: "hidden", background: "#111" }}>
                    
                    <div className="flex" style={{ minHeight: 480 }}>
                        <div className="flex-1 p-4" style={{ background: "#0d0d0d" }}>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 h-full" style={{ gridTemplateRows: "auto 1fr auto" }}>
                                <div className="flex items-center justify-center p-2" style={{ border: "1px solid #3a3a3a", borderRadius: 6, background: "#0a0a0a" }}>
                                    <div className="w-24 h-32">
                                        <PistonGraphic phase={phase * 3} />
                                    </div>
                                </div>
                                <div className="flex items-center justify-center p-2" style={{ border: "1px solid #3a3a3a", borderRadius: 6, background: "#0a0a0a" }}>
                                    <div className="w-28 h-28">
                                        <ClutchPlateGraphic rotation={tick * 0.3} />
                                    </div>
                                </div>
                                <div className="hidden md:flex items-center justify-center p-2" style={{ border: "1px solid #3a3a3a", borderRadius: 6, background: "#0a0a0a" }}>
                                    <div className="w-24 h-32">
                                        <RadiatorGraphic />
                                    </div>
                                </div>
                                <div className="col-span-2 md:col-span-3 flex items-center justify-center p-3"
                                    style={{ border: "1px solid #3a3a3a", borderRadius: 6, background: "#0a0a0a", position: "relative", overflow: "hidden" }}>
                                    <div style={{ width: "100%", height: 380 }}>
                                        <Drone3DViewer
                                            rpm={rpm}
                                            throttle={throttle}
                                            vibration={liveTelemetry?.vibration ?? 0}
                                            cht={cht}
                                            egt={egt}
                                            oilTemperature={oilTemp}
                                            faultFamily={advisory?.fault_family}
                                            advisoryLevel={advisory?.level}
                                            advisoryTitle={advisory?.title}
                                            height={380}
                                        />
                                    </div>
                                </div>
                                <div className="col-span-2 md:col-span-3 flex flex-col gap-2">

                                {/* ENGINE SIGNALS: cells + RPM gauge */}
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                                <div className="md:col-span-3 flex flex-col gap-2">

                                    <div
                                        className="text-xs font-semibold"
                                        style={{ fontFamily: "'JetBrains Mono', monospace", color: "#c0c0c0", letterSpacing: 1 }}
                                    >
                                        ENGINE SIGNALS
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                        <TelemetryCell label="TIME" value={timeStr} unit="" color="#3b82f6" />
                                        <TelemetryCell label="TORQUE" value={torque} unit="N·m"/>
                                        <TelemetryCell label="FUEL FLOW" value={fuelFlow} unit="kg/h"/>
                                        <TelemetryCell label="VIBRATION" value={vibration} unit="g"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                        <TelemetryCell label="CHT" value={cht} unit="°C" />
                                        <TelemetryCell label="EGT" value={egt} unit="°C" />
                                        <TelemetryCell label="OIL TEMP" value={oilTemp} unit="°C"/>
                                        <TelemetryCell label="OIL PRESSURE" value={oilPressure} unit="psi"/>
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                        <TelemetryCell
                                            label="BATTERY VOLTAGE"
                                            value={formatOptional(batteryVoltage, 2)}
                                            unit="V"
                                        />
                                        <TelemetryCell
                                            label="ALTERNATOR CURRENT"
                                            value={formatOptional(alternatorCurrent, 1)}
                                            unit="A"
                                        />
                                        <TelemetryCell
                                            label="INJECTION TIMING"
                                            value={formatOptional(injectionTiming, 1)}
                                            unit="° BTDC"
                                        />
                                        <TelemetryCell
                                            label="INJECTION DURATION"
                                            value={formatOptional(injectionDuration, 2)}
                                            unit="ms"
                                        />
                                    </div>

                                </div>

                                {/* RPM GAUGE */}
                                <div
                                    className="flex items-center justify-center"
                                    style={{
                                        border: "1px solid #3a3a3a",
                                        borderRadius: 6,
                                        background: "#0a0a0a",
                                        minHeight: 180,
                                    }}
                                >
                                    <div style={{ width: 250, height: 250 }}>
                                        <AnalogGauge
                                            value={rpm}
                                            max={5000}
                                            label="RPM"
                                            unit="RPM"
                                            majorTicks={10}
                                            minorPerMajor={5}
                                            lowerRedZone={3200}
                                            redZone={4800}
                                        />
                                    </div>
                                </div>
                                </div>

                                {/* FLIGHT CONDITIONS: full width */}
                                    <div
                                        className="mt-2 text-xs font-semibold flex flex-wrap justify-between gap-2"
                                        style={{ fontFamily: "'JetBrains Mono', monospace", color: "#a78bfa", letterSpacing: 1 }}
                                    >
                                        <span>FLIGHT CONDITIONS</span>
                                        <span style={{ color: "#c0c0c0" }}>
                                            {profile ? `PROFILE: ${profile.label.toUpperCase()}` : ""}
                                        </span>
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                        <TelemetryCell
                                            label="THROTTLE"
                                            value={throttle}
                                            unit="%"
                                            color="#a78bfa"
                                        />
                                        <TelemetryCell
                                            label="ENGINE LOAD"
                                            value={engineLoad}
                                            unit="%"
                                            color="#a78bfa"
                                        />
                                        <TelemetryCell
                                            label="ALTITUDE"
                                            value={altitude}
                                            unit="m"
                                            color="#a78bfa"
                                        />
                                        <TelemetryCell
                                            label="AMBIENT TEMP"
                                            value={ambientTemp}
                                            unit="°C"
                                            color="#a78bfa"
                                        />
                                    </div>

                            </div>
                                
                            </div>
                        </div>

                        
                    </div>
                </div>
            </div>
        </section>
    );
}

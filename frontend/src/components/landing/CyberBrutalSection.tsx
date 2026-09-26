import { useState, useEffect } from "react";
import { Radio, ArrowUpRight } from "lucide-react";
import DroneRadarGraphic from "./DroneRadarGraphic";
import { Link } from "react-router-dom";

function useClock(): Date {
    const [t, setT] = useState<Date>(new Date());

    useEffect(() => {
        const id = setInterval(() => setT(new Date()), 1000);
        return () => clearInterval(id);
    }, []);

    return t;
}

const pad = (n: number): string =>
    n.toString().padStart(2, "0");

export default function CyberBrutalSection({ onViewTwin, onScrollToDrone, onScrollToHud }: { onViewTwin: () => void; onScrollToDrone: () => void; onScrollToHud: () => void }) {
    const time = useClock();
    const [glitch, setGlitch] = useState(false);


    return (
        <section style={{ background: "#050505", color: "#e8e8e8", fontFamily: "'Space Grotesk', sans-serif" }} className="relative overflow-hidden">
            <div
                className="pointer-events-none absolute inset-0 opacity-[0.35]"
                style={{
                    backgroundImage: "linear-gradient(to right, #161616 1px, transparent 1px), linear-gradient(to bottom, #161616 1px, transparent 1px)",
                    backgroundSize: "42px 42px",
                }}
            />

            <div className="relative z-10 flex items-center justify-between px-6 md:px-10 py-5 border-b" style={{ borderColor: "#3a3a3a" }}>
                <div className="flex items-center gap-2">
                    <span style={{ background: "#C6FF3D" }} className="w-3 h-3 inline-block" />
                    <span className="tracking-tight font-bold text-3xl" style={{ color: "#fff" }}>SKOPEO</span>
                </div>
                <div className="hidden md:flex items-center gap-8 text-l" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#d0d0d0" }}>
                    <span className="hover:text-white cursor-pointer transition" onClick={onScrollToDrone}>OVERVIEW</span>
                    <span className="hover:text-white cursor-pointer transition" onClick={onScrollToHud}>TELEMETRY</span>
                    <span className="hover:text-white cursor-pointer transition" onClick={onScrollToHud}>DIAGNOSTICS</span>
                </div>
                <div className="flex items-center gap-4">
                    <span className="hidden sm:inline text-sm" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#b0b0b0" }}>
                        {pad(time.getHours())}:{pad(time.getMinutes())}:{pad(time.getSeconds())}
                    </span>
                </div>
            </div>

            <div className="relative z-10 grid md:grid-cols-2 gap-10 px-6 md:px-10 py-16 md:py-24 items-center">
                <div>
                    <div className="inline-block text-xs mb-6 px-2 py-1" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#C6FF3D", border: "1px solid #4a6a10" }}>
                        &nbsp; DIGITAL TWIN PLATFORM
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
                    <p className="max-w-md mb-8" style={{ color: "#d0d0d0", fontSize: "1.125rem", lineHeight: 1.7 }}>
                        A live physics-informed twin of the engine, fed by nine sensor channels,
                        scoring faults and re-estimating remaining useful life every cycle.
                    </p>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={onViewTwin}
                            style={{
                                background: "#C6FF3D",
                                color: "#050505",
                                cursor: "pointer",
                            }}
                            className="font-bold px-8 py-4 text-base hover:brightness-110 transition"
                        >
                            VIEW LIVE TWIN
                        </button>

                        <Link
                            to="/analysis"
                            className="
                                flex items-center gap-2
                                px-8 py-4
                                text-base font-bold
                                text-white
                                border border-[#666]
                                hover:border-[#C6FF3D]
                                hover:text-[#C6FF3D]
                                transition
                            "
                        >
                            ANALYSIS
                            <ArrowUpRight size={17} />
                        </Link>
                    </div>
                </div>

                <div className="relative" style={{ border: "1px solid #3a3a3a", background: "#0a0a0a" }}>
                    <div className="flex items-center justify-between px-4 py-2 text-sm" style={{ borderBottom: "1px solid #3a3a3a", fontFamily: "'JetBrains Mono', monospace", color: "#c0c0c0" }}>
                        <span className="flex items-center gap-1.5"><Radio size={11} />&gt;DRONE_RADAR</span>
                        <Radio size={12} color="#C6FF3D" />
                    </div>
                    <div className="h-64 md:h-80">
                        <DroneRadarGraphic />
                    </div>
                </div>
            </div>

        </section>
    );
}
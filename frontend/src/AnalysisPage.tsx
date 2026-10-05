import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeft, Clock3, Trash2 } from "lucide-react";
import {
    getMissions,
    getMission,
    getMissionTelemetry,
    getMissionReplay,
    getMissionReport,
    getMissionBaseline,
} from "./services/api";
import type {
    MissionItem,
    MissionSummary,
    TelemetryData,
    MissionReplayResponse,
    MissionBaseline,
    MissionReport as MissionReportData,
} from "./types/api";
import { HealthTab, SignalsTab, SummaryTab, type SignalsSub } from "./components/analysis/AnalysisTabs";
import ReplayTab from "./components/analysis/ReplayTab";
import {
    SUBSYSTEMS,
    buildMissionModel,
    clock,
    weakestSubsystem,
    type SubsystemKey,
} from "./components/analysis/missionData";
import ResetDataDialog from "./components/analysis/ResetDataDialog";

const TABS = [
    { key: "summary", label: "SUMMARY" },
    { key: "signals", label: "SIGNALS" },
    { key: "health", label: "HEALTH & RUL" },
    { key: "replay", label: "REPLAY" },
] as const;
type TabKey = typeof TABS[number]["key"];

const SIGNAL_SUBS: SignalsSub[] = [...SUBSYSTEMS.map((s) => s.key), "efficiency"];

export default function AnalysisPage() {
    // Mission, tab and signals sub-tab live in the URL so views are linkable.
    const [params, setParams] = useSearchParams();
    const selectedMission = params.get("mission") ?? "";
    const tab: TabKey = (TABS.find((t) => t.key === params.get("tab"))?.key) ?? "summary";
    const subParam = params.get("sub") as SignalsSub | null;

    const setParam = useCallback((updates: Record<string, string | null>) => {
        setParams((prev) => {
            const next = new URLSearchParams(prev);
            Object.entries(updates).forEach(([k, v]) => (v == null ? next.delete(k) : next.set(k, v)));
            return next;
        });
    }, [setParams]);
    const setSelectedMission = (id: string) => setParam({ mission: id, sub: null });

    // Shared "current moment" (sample index): the replay position and the
    // cursor line on every chart.
    const [cursorIndex, setCursorIndex] = useState(0);
    const [missions, setMissions] = useState<MissionItem[]>([]);
    const [mission, setMission] = useState<MissionSummary | null>(null);
    const [telemetry, setTelemetry] = useState<TelemetryData[]>([]);
    const [replay, setReplay] = useState<MissionReplayResponse | null>(null);
    const [report, setReport] = useState<MissionReportData | null>(null);
    const [baseline, setBaseline] = useState<MissionBaseline | null>(null);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [resetOpen, setResetOpen] = useState(false);
    const [missionsVersion, setMissionsVersion] = useState(0);

    useEffect(() => {
        async function loadMissions() {
            try {
                setLoading(true);
                setError(null);

                const result = await getMissions();

                setMissions(result.missions);

                const current = params.get("mission");
                if (result.missions.length === 0) {
                    setMission(null);
                    if (current) setParam({ mission: null, sub: null });
                } else if (!current || !result.missions.some((m) => m.mission_id === current)) {
                    setParam({ mission: result.missions[0].mission_id, sub: null });
                }
            } catch (err) {
                setError(
                    err instanceof Error
                        ? err.message
                        : "Failed to load missions"
                );
            } finally {
                setLoading(false);
            }
        }

        loadMissions();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [missionsVersion]);

    // After a reset, reload the mission list; the selection moves to the
    // newest remaining mission (or clears when none are left).
    const onDataDeleted = () => {
        setResetOpen(false);
        setMission(null);
        setTelemetry([]);
        setReplay(null);
        setReport(null);
        setBaseline(null);
        setParam({ mission: null, sub: null });
        setMissionsVersion((v) => v + 1);
    };

    useEffect(() => {
        if (!selectedMission) return;

        async function loadMissionData() {
            try {
                setLoading(true);
                setError(null);

                const missionData = await getMission(selectedMission);

                const [
                    telemetryData,
                    replayData,
                    reportData,
                    baselineData,
                ] = await Promise.all([
                    getMissionTelemetry(selectedMission),
                    getMissionReplay(selectedMission),
                    // A mission without health data still has a report.
                    getMissionReport(selectedMission).catch(() => null),
                    // Charts work without expected-healthy lines.
                    getMissionBaseline(selectedMission).catch(() => null),
                ]);

                setMission(missionData);
                setTelemetry(telemetryData);
                setReplay(replayData);
                setCursorIndex(0);
                setReport(reportData);
                setBaseline(baselineData);
            } catch (err) {
                setError(
                    err instanceof Error
                        ? err.message
                        : "Failed to load mission data"
                );
            } finally {
                setLoading(false);
            }
        }

        loadMissionData();
    }, [selectedMission]);

    const model = useMemo(
        () => buildMissionModel(telemetry, replay?.points ?? [], baseline, report),
        [telemetry, replay, baseline, report],
    );
    const sub: SignalsSub = subParam && SIGNAL_SUBS.includes(subParam)
        ? subParam
        : weakestSubsystem(model.rows) ?? "thermal";
    const cursorX = model.rows[cursorIndex]?.x ?? null;

    const selectX = useCallback((x: number) => {
        const i = model.rows.findIndex((r) => r.x >= x);
        setCursorIndex(i < 0 ? model.rows.length - 1 : i);
    }, [model.rows]);

    // From a subsystem (summary card or replay bar) to its signals.
    const openSubsystem = (key: SubsystemKey, atX?: number) => {
        if (atX != null) selectX(atX);
        setParam({ tab: "signals", sub: key });
    };

    if (loading && !mission) {
        return (
            <div
                className="min-h-screen flex items-center justify-center"
                style={{
                    background: "#050505",
                    color: "#C6FF3D",
                    fontFamily: "'JetBrains Mono', monospace",
                }}
            >
                LOADING MISSION DATA...
            </div>
        );
    }

    return (
        <div
            className="min-h-screen"
            style={{
                background: "#050505",
                color: "#e8e8e8",
                fontFamily: "'Space Grotesk', sans-serif",
            }}
        >
            {/* Header */}
            <header
                className="flex items-center justify-between px-6 md:px-10 py-5"
                style={{
                    borderBottom: "1px solid #3a3a3a",
                    background: "#080808",
                }}
            >
                <div className="flex items-center gap-3">
                    <span
                        className="w-3 h-3 inline-block"
                        style={{ background: "#C6FF3D" }}
                    />

                    <span
                        className="font-bold text-xl"
                        style={{ color: "#fff" }}
                    >
                        SKOPEO
                    </span>

                    <span style={{ color: "#555" }}>/</span>

                    <span
                        className="text-sm"
                        style={{
                            color: "#C6FF3D",
                            fontFamily: "'JetBrains Mono', monospace",
                        }}
                    >
                        MISSION_ANALYSIS
                    </span>
                </div>

                <a
                    href="/"
                    className="flex items-center gap-2 px-3 py-2 text-sm transition hover:bg-white/10"
                    style={{
                        border: "1px solid #444",
                        color: "#ccc",
                        fontFamily: "'JetBrains Mono', monospace",
                    }}
                >
                    <ArrowLeft size={14} />
                    LIVE TWIN
                </a>
            </header>

            {resetOpen && (
                <ResetDataDialog
                    missionId={selectedMission}
                    missionCount={missions.length}
                    onClose={() => setResetOpen(false)}
                    onDeleted={onDataDeleted}
                />
            )}

            <main className="px-6 md:px-10 py-8">
                {/* Page heading */}
                <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-5 mb-8">
                    <div>
                        <div
                            className="text-xs mb-2"
                            style={{
                                color: "#C6FF3D",
                                fontFamily: "'JetBrains Mono', monospace",
                            }}
                        >
                            HISTORICAL ENGINE DATA
                        </div>

                        <h1
                            className="font-bold"
                            style={{
                                fontSize: "clamp(2rem, 5vw, 3.5rem)",
                                color: "#fff",
                                lineHeight: 1,
                            }}
                        >
                            MISSION ANALYSIS
                        </h1>
                    </div>

                    <div className="flex items-center gap-3">
                        <span
                            className="text-sm"
                            style={{
                                color: "#888",
                                fontFamily: "'JetBrains Mono', monospace",
                            }}
                        >
                            MISSION
                        </span>

                        <select
                            value={selectedMission}
                            onChange={(e) =>
                                setSelectedMission(e.target.value)
                            }
                            className="px-4 py-2 outline-none"
                            style={{
                                background: "#111",
                                border: "1px solid #555",
                                color: "#fff",
                                fontFamily: "'JetBrains Mono', monospace",
                            }}
                        >
                            {missions.map((item) => (
                                <option
                                    key={item.mission_id}
                                    value={item.mission_id}
                                >
                                    {item.mission_id}
                                </option>
                            ))}
                        </select>

                        <button
                            onClick={() => setResetOpen(true)}
                            className="flex items-center gap-2 px-3 py-2 text-sm transition hover:bg-white/10"
                            style={{
                                border: "1px solid #e8543f",
                                color: "#e8543f",
                                fontFamily: "'JetBrains Mono', monospace",
                            }}
                        >
                            <Trash2 size={14} />
                            RESET DATA
                        </button>
                    </div>
                </div>

                {error && (
                    <div
                        className="mb-6 p-4"
                        style={{
                            border: "1px solid #e8543f",
                            background: "rgba(232,84,63,0.08)",
                            color: "#e8543f",
                            fontFamily: "'JetBrains Mono', monospace",
                        }}
                    >
                        {error}
                    </div>
                )}

                {/* Mission summary */}
                {mission && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                        <div
                            className="p-4"
                            style={{
                                border: "1px solid #3a3a3a",
                                background: "#0e0e0e",
                            }}
                        >
                            <div
                                className="text-xs mb-2"
                                style={{
                                    color: "#777",
                                    fontFamily: "'JetBrains Mono', monospace",
                                }}
                            >
                                ENGINE
                            </div>

                            <div
                                className="text-lg font-bold"
                                style={{ color: "#fff" }}
                            >
                                {mission.engine_id}
                            </div>
                        </div>

                        <div
                            className="p-4"
                            style={{
                                border: "1px solid #3a3a3a",
                                background: "#0e0e0e",
                            }}
                        >
                            <div
                                className="text-xs mb-2"
                                style={{
                                    color: "#777",
                                    fontFamily: "'JetBrains Mono', monospace",
                                }}
                            >
                                SAMPLES
                            </div>

                            <div
                                className="text-lg font-bold"
                                style={{ color: "#fff" }}
                            >
                                {mission.sample_count.toLocaleString()}
                            </div>
                        </div>

                        <div
                            className="p-4"
                            style={{
                                border: "1px solid #3a3a3a",
                                background: "#0e0e0e",
                            }}
                        >
                            <div
                                className="text-xs mb-2"
                                style={{
                                    color: "#777",
                                    fontFamily: "'JetBrains Mono', monospace",
                                }}
                            >
                                TIME RANGE
                            </div>

                            <div
                                className="flex items-center gap-2 text-sm"
                                style={{
                                    color: "#fff",
                                    fontFamily: "'JetBrains Mono', monospace",
                                }}
                            >
                                <Clock3 size={14} />
                                {new Date(mission.start_time).toLocaleTimeString()}
                                {" — "}
                                {new Date(mission.end_time).toLocaleTimeString()}
                            </div>
                        </div>
                    </div>
                )}

                {/* Tabs */}
                <div className="sticky top-0 z-20 -mx-6 md:-mx-10 px-6 md:px-10 mb-6 flex flex-wrap items-center gap-1" style={{ background: "#050505", borderBottom: "1px solid #3a3a3a" }}>
                    {TABS.map((t) => (
                        <button
                            key={t.key}
                            onClick={() => setParam({ tab: t.key })}
                            className="px-5 py-3 text-sm font-bold transition"
                            style={{
                                fontFamily: "'JetBrains Mono', monospace",
                                color: tab === t.key ? "#C6FF3D" : "#888",
                                borderBottom: `2px solid ${tab === t.key ? "#C6FF3D" : "transparent"}`,
                                marginBottom: -1,
                            }}
                        >
                            {t.label}
                        </button>
                    ))}
                    {tab !== "summary" && cursorX != null && (
                        <span className="ml-auto text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#888" }}>
                            CURSOR <span style={{ color: "#fff", fontWeight: 700 }}>{clock(cursorX)}</span> · click any chart to move it
                        </span>
                    )}
                </div>

                {tab === "summary" && <SummaryTab model={model} report={report} onOpenSubsystem={openSubsystem} />}
                {tab === "signals" && (
                    <SignalsTab model={model} cursorX={cursorX} onSelectX={selectX} sub={sub} onSub={(next) => setParam({ sub: next })} />
                )}
                {tab === "health" && <HealthTab model={model} cursorX={cursorX} onSelectX={selectX} />}
                {tab === "replay" && (
                    <ReplayTab
                        model={model}
                        report={report}
                        cursorIndex={cursorIndex}
                        onCursorIndex={setCursorIndex}
                        onOpenSubsystem={(key) => openSubsystem(key)}
                    />
                )}
            </main>
        </div>
    );
}
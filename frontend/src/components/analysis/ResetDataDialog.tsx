import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { deleteAllMissions, deleteMission } from "../../services/api";

type Scope = "mission" | "all";

const MONO = "'JetBrains Mono', monospace";
const DANGER = "#e8543f";

// Two-step reset: choose what to delete, then confirm a warning that names
// exactly what goes. Deletions are permanent.
export default function ResetDataDialog({
    missionId,
    missionCount,
    onClose,
    onDeleted,
}: {
    missionId: string;
    missionCount: number;
    onClose: () => void;
    onDeleted: (scope: Scope) => void;
}) {
    const [scope, setScope] = useState<Scope | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const confirm = async () => {
        if (!scope) return;
        setBusy(true);
        setError(null);
        try {
            if (scope === "mission") await deleteMission(missionId);
            else await deleteAllMissions();
            onDeleted(scope);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
            setBusy(false);
        }
    };

    const option = (value: Scope, title: string, detail: string, disabled = false) => (
        <button
            onClick={() => setScope(value)}
            disabled={disabled}
            className="w-full text-left p-4 transition hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ border: "1px solid #444", background: "#111" }}
        >
            <div className="font-bold" style={{ color: "#fff" }}>{title}</div>
            <div className="text-xs mt-1" style={{ color: "#888", fontFamily: MONO }}>{detail}</div>
        </button>
    );

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.75)" }}
            onClick={busy ? undefined : onClose}
        >
            <div
                className="w-full max-w-lg p-6"
                style={{ background: "#0b0b0b", border: "1px solid #3a3a3a" }}
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="reset-title"
            >
                <div className="flex items-center justify-between mb-5">
                    <div id="reset-title" className="text-sm" style={{ color: "#C6FF3D", fontFamily: MONO }}>
                        RESET DATA
                    </div>
                    <button onClick={onClose} disabled={busy} aria-label="Close" style={{ color: "#888" }}>
                        <X size={18} />
                    </button>
                </div>

                {!scope ? (
                    <div className="space-y-3">
                        {option(
                            "mission",
                            "Delete this mission",
                            missionId || "No mission selected",
                            !missionId,
                        )}
                        {option(
                            "all",
                            "Delete all missions",
                            `${missionCount} mission${missionCount === 1 ? "" : "s"}: a fresh start`,
                            missionCount === 0,
                        )}
                    </div>
                ) : (
                    <div>
                        <div className="flex gap-3 p-4 mb-5" style={{ border: `1px solid ${DANGER}`, background: "rgba(232,84,63,0.08)" }}>
                            <AlertTriangle size={20} style={{ color: DANGER, flexShrink: 0 }} />
                            <div className="text-sm" style={{ color: "#f1c7c0" }}>
                                {scope === "mission" ? (
                                    <>This permanently deletes <b>all data for mission {missionId}</b>: telemetry, health history, predictions and its report.</>
                                ) : (
                                    <>This permanently deletes <b>all {missionCount} missions</b>: every mission's telemetry, health history, predictions and reports.</>
                                )}{" "}
                                It can't be undone.
                            </div>
                        </div>

                        {error && (
                            <div className="text-sm mb-4" style={{ color: DANGER, fontFamily: MONO }}>{error}</div>
                        )}

                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => { setScope(null); setError(null); }}
                                disabled={busy}
                                className="px-4 py-2 text-sm transition hover:bg-white/10"
                                style={{ border: "1px solid #444", color: "#ccc", fontFamily: MONO }}
                            >
                                BACK
                            </button>
                            <button
                                onClick={confirm}
                                disabled={busy}
                                className="px-4 py-2 text-sm font-bold transition hover:brightness-110 disabled:opacity-60"
                                style={{ background: DANGER, color: "#fff", fontFamily: MONO }}
                            >
                                {busy ? "DELETING..." : scope === "mission" ? "DELETE MISSION" : "DELETE ALL MISSIONS"}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

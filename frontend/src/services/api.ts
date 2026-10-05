import type {
    EngineItem,
    MissionItem,
    MissionSummary,
    TelemetryData,
    EngineHealthResponse,
    HealthHistoryResponse,
    AlertData,
    DashboardResponse,
    MissionReplayResponse,
    MissionReport,
    MissionBaseline,
} from "../types/api";

const BASE_URL = "http://localhost:8000/api";
const WS_BASE_URL = "ws://localhost:8000/ws";

async function request<T>(
    endpoint: string,
    options?: RequestInit
): Promise<T> {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
        headers: {
            "Content-Type": "application/json",
        },
        ...options,
    });

    if (!res.ok) {
        let errorDetail = `HTTP ${res.status} ${res.statusText}`;

        try {
            const json = await res.json();

            if (json.detail) {
                errorDetail = json.detail;
            }
        } catch {}

        throw new Error(errorDetail);
    }

    return res.json();
}

export async function getEngines(): Promise<{
    engines: EngineItem[];
}> {
    return request<{ engines: EngineItem[] }>("/engines");
}

export async function getEngine(
    engineId: string
): Promise<EngineItem> {
    return request<EngineItem>(
        `/engines/${encodeURIComponent(engineId)}`
    );
}

export async function getLatestTelemetry(
    engineId: string,
    missionId?: string
): Promise<TelemetryData> {
    const query = missionId
        ? `?mission_id=${encodeURIComponent(missionId)}`
        : "";

    return request<TelemetryData>(
        `/engines/${encodeURIComponent(engineId)}/telemetry/latest${query}`
    );
}

export async function getEngineHealth(
    engineId: string,
    missionId?: string
): Promise<EngineHealthResponse> {
    const query = missionId
        ? `?mission_id=${encodeURIComponent(missionId)}`
        : "";

    return request<EngineHealthResponse>(
        `/engines/${encodeURIComponent(engineId)}/health${query}`
    );
}

export async function getEngineHealthHistory(
    engineId: string,
    missionId?: string
): Promise<HealthHistoryResponse> {
    const query = missionId
        ? `?mission_id=${encodeURIComponent(missionId)}`
        : "";

    return request<HealthHistoryResponse>(
        `/engines/${encodeURIComponent(engineId)}/health/history${query}`
    );
}

export async function getEngineAlerts(
    engineId: string,
    missionId?: string
): Promise<AlertData[]> {
    const query = missionId
        ? `?mission_id=${encodeURIComponent(missionId)}`
        : "";

    return request<AlertData[]>(
        `/engines/${encodeURIComponent(engineId)}/alerts${query}`
    );
}

export async function getMissions(): Promise<{
    missions: MissionItem[];
}> {
    return request<{ missions: MissionItem[] }>("/missions");
}

// Permanently deletes a mission's telemetry, health snapshots and ingestion
// events. The backend refuses while that mission is being simulated.
export async function deleteMission(
    missionId: string
): Promise<{ deleted_missions: number }> {
    return request<{ deleted_missions: number }>(
        `/missions/${encodeURIComponent(missionId)}`,
        { method: "DELETE" }
    );
}

// Permanently deletes every mission. Refused while a simulation is running.
export async function deleteAllMissions(): Promise<{ deleted_missions: number }> {
    return request<{ deleted_missions: number }>("/missions", { method: "DELETE" });
}

export async function getMissionReport(
    missionId: string
): Promise<MissionReport> {
    return request<MissionReport>(
        `/missions/${encodeURIComponent(missionId)}/report`
    );
}

export async function getMissionBaseline(
    missionId: string
): Promise<MissionBaseline> {
    return request<MissionBaseline>(
        `/missions/${encodeURIComponent(missionId)}/baseline`
    );
}

export async function getMission(
    missionId: string
): Promise<MissionSummary> {
    return request<MissionSummary>(
        `/missions/${encodeURIComponent(missionId)}`
    );
}

export async function getMissionTelemetry(
    missionId: string,
    start?: string,
    end?: string
): Promise<TelemetryData[]> {
    const params = new URLSearchParams();

    if (start) {
        params.append("start", start);
    }

    if (end) {
        params.append("end", end);
    }

    const query = params.toString()
        ? `?${params.toString()}`
        : "";

    return request<TelemetryData[]>(
        `/missions/${encodeURIComponent(missionId)}/telemetry${query}`
    );
}

export async function getMissionReplay(
    missionId: string
): Promise<MissionReplayResponse> {
    return request<MissionReplayResponse>(
        `/missions/${encodeURIComponent(missionId)}/replay`
    );
}

export async function getDashboard(
    engineId: string,
    missionId?: string
): Promise<DashboardResponse> {
    const query = missionId
        ? `?mission_id=${encodeURIComponent(missionId)}`
        : "";

    return request<DashboardResponse>(
        `/dashboard/${encodeURIComponent(engineId)}${query}`
    );
}

export function getEngineWebSocketUrl(
    engineId: string,
    missionId?: string
): string {
    const query = missionId
        ? `?mission_id=${encodeURIComponent(missionId)}`
        : "";

    return `${WS_BASE_URL}/engines/${encodeURIComponent(engineId)}${query}`;
}

// ---------------------------------------------------------
// Simulation control
// ---------------------------------------------------------

export async function startSimulation(
    engineId: string,
    profile: string
): Promise<{
    status: string;
    pid?: number;
    profile?: string;
    mission_id?: string;
    fault_id?: number;
}> {
    return request(
        `/engines/${encodeURIComponent(engineId)}/simulation/start` +
            `?profile=${encodeURIComponent(profile)}`,
        {
            method: "POST",
        }
    );
}

export async function stopSimulation(
    engineId: string
): Promise<{
    status: string;
}> {
    return request(
        `/engines/${encodeURIComponent(engineId)}/simulation/stop`,
        {
            method: "POST",
        }
    );
}

export async function getSimulationStatus(engineId: string): Promise<{
    status: "running" | "stopped";
    pid?: number;
    profile?: string;
    mission_id?: string;
}> {
    return request(
        `/engines/${encodeURIComponent(engineId)}/simulation/status`,
        {
            method: "GET",
        }
    );
}

export async function injectFault(
    engineId: string,
    faultId: number
): Promise<{
    engine_id: string;
    fault_id: number;
    status: string;
}> {
    return request(
        `/engines/${encodeURIComponent(engineId)}/fault?fault_id=${faultId}`,
        {
            method: "POST",
        }
    );
}
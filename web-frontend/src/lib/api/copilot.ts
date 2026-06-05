import { api, API_BASE } from "./client";
import { getToken } from "./token";

export interface CopilotInsightOut {
  insights: string[];
}

export interface CopilotExample {
  query: string;
  category: string;
  description: string;
  tables: string[];
}

export interface CopilotResponse {
  query: string;
  intent: string;
  narrative: string;
  confidence: number;
  data_context: {
    chart?: { label: string; value: number }[];
    [key: string]: unknown;
  };
  tools_invoked: Array<{
    tool_name: string;
    parameters: Record<string, unknown>;
    result_summary?: string;
  }>;
  follow_up_suggestions: string[];
}

export const copilotApi = {
  ask: (query: string, context?: Record<string, unknown>) =>
    api<CopilotResponse>("/api/v1/copilot/query", {
      method: "POST",
      body: { query, context: context ?? {} },
    }),
  getExamples: () => api<CopilotExample[]>("/api/v1/copilot/examples"),
  getDashboardInsights: () => api<CopilotInsightOut>("/api/v1/copilot/insights/dashboard"),
  getProductInsights: (sku: string, warehouseId?: number) => {
    const q = new URLSearchParams();
    if (warehouseId !== undefined) q.set("warehouse_id", String(warehouseId));
    const query = q.toString();
    return api<CopilotInsightOut>(
      `/api/v1/copilot/insights/products/${encodeURIComponent(sku)}${query ? `?${query}` : ""}`,
    );
  },
  getForecastInsights: (params?: { warehouse?: string; category?: string; period?: string }) => {
    const q = new URLSearchParams();
    if (params?.warehouse) q.set("warehouse", params.warehouse);
    if (params?.category) q.set("category", params.category);
    if (params?.period) q.set("period", params.period);
    const query = q.toString();
    return api<CopilotInsightOut>(`/api/v1/copilot/insights/forecast${query ? `?${query}` : ""}`);
  },
};

export type CopilotStreamEvent = {
  type:
    | "connection"
    | "version"
    | "received"
    | "intent"
    | "tool_call"
    | "data"
    | "narrative"
    | "done"
    | "error"
    | "raw";
  content?: string;
  reason?: string;
  confidence?: number;
};

export function openCopilotSocket() {
  const token = getToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";

  const apiBase = API_BASE || "http://127.0.0.1:8000";
  const apiUrl = new URL(apiBase, window.location.origin);

  apiUrl.protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";

  const wsBase = apiUrl.toString().replace(/\/$/, "");
  const wsUrl = `${wsBase}/api/v1/copilot/ws${query}`;

  console.log("Copilot WS URL:", wsUrl);

  return new WebSocket(wsUrl);
}

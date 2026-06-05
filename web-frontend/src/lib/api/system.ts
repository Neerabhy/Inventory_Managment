import { api } from "./client";

export interface HealthService {
  name: string;
  status: "healthy" | "degraded" | "down";
  uptime_pct?: number;
}

export interface HealthStatus {
  status: string;
  database: string;
  ml_models_loaded: boolean;
  timestamp: string;
  services?: HealthService[];
}

export const systemApi = {
  health: () => api<HealthStatus>("/health"),
};

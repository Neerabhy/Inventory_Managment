import { API_BASE } from "./client";
import { getToken } from "./token";
import { api } from "./client";

export type ReportType = "executive" | "inventory" | "supplier" | "logistics" | "forecast";
export type ReportFormat = "html" | "csv";

export interface ReportEmailResponse {
  sent: boolean;
  status: string;
  report_type: string;
  email: string;
  outbox_path?: string | null;
}

export async function downloadReport(reportType: ReportType, format: ReportFormat) {
  const token = getToken();
  const url = `${API_BASE}/api/v1/reports/download?report_type=${encodeURIComponent(reportType)}&format=${format}`;
  const res = await fetch(url, {
    headers: {
      Accept: format === "csv" ? "text/csv" : "text/html",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = `${reportType}-report.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

export const reportsApi = {
  download: downloadReport,
  email: (email: string, reportType: ReportType, format: ReportFormat = "html") =>
    api<ReportEmailResponse>("/api/v1/reports/email", {
      method: "POST",
      body: { email, report_type: reportType, format },
    }),
};

import { api } from "./client";

export interface ReturnRecord {
  id: number;
  product_id: number;
  sale_id: number | null;
  customer_id: number | null;
  reason_code: string | null;
  refund_amount: number | null;
  reverse_logistics_cost: number | null;
  gross_margin_lost: number;
  estimated_return_loss: number;
  fraud_score: number | null;
  return_ratio: number | null;
  risk_label: string | null;
  anomaly_flag: boolean;
  status: string;
  approved_by: string | null;
  override_note: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface ReturnsSummary {
  total_returns: number;
  sales_orders: number;
  pending: number;
  approved: number;
  declined: number;
  high_risk: number;
  anomaly_flagged: number;
  approval_rate_pct: number;
  return_rate_pct: number;
  gross_margin_lost: number;
  reverse_logistics_cost: number;
  estimated_return_loss: number;
}

export interface ReturnHistoryRecord {
  id: number;
  return_id: number;
  product_id: number;
  customer_id: number | null;
  reason_code: string | null;
  refund_amount: number | null;
  action: string;
  approved_by: string | null;
  override_note: string | null;
  created_at: string;
}

export const returnsApi = {
  listReturns: (params?: { status?: string; risk_label?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.risk_label) q.set("risk_label", params.risk_label);
    if (params?.skip !== undefined) q.set("skip", String(params.skip));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return api<ReturnRecord[]>(`/api/v1/returns/?${q}`);
  },

  getHistory: (params?: { skip?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.skip !== undefined) q.set("skip", String(params.skip));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return api<ReturnHistoryRecord[]>(`/api/v1/returns/history?${q}`);
  },

  getReturn: (id: number) => api<ReturnRecord>(`/api/v1/returns/${id}`),

  approveReturn: (id: number, override_note?: string) =>
    api<ReturnRecord>(`/api/v1/returns/${id}/approve`, {
      method: "POST",
      body: { override_note: override_note ?? null },
    }),

  declineReturn: (id: number, override_note: string) =>
    api<ReturnRecord>(`/api/v1/returns/${id}/decline`, {
      method: "POST",
      body: { override_note },
    }),

  summary: () => api<ReturnsSummary>("/api/v1/returns/analytics/summary"),
};

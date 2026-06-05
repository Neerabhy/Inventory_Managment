import { api } from "./client";

export interface RevenuePoint {
  day: string;
  revenue: number;
  orders: number;
  units: number;
}

export interface ProductSalesPoint {
  day: string;
  revenue: number;
  units: number;
}

export interface CategoryPoint {
  category: string;
  revenue: number;
}

export interface ReturnReasonPoint {
  reason: string;
  count: number;
}

export interface DelayBucketPoint {
  bucket: string;
  value: number;
}

export interface DashboardAnalyticsOut {
  revenueTrend: RevenuePoint[];
  categoryPerf: CategoryPoint[];
  returnReasons: ReturnReasonPoint[];
  shipmentDelayBuckets: DelayBucketPoint[];
}

export interface DashboardSummary {
  total_revenue: number;
  sales_orders: number;
  units_sold: number;
  return_rate_pct: number;
  inventory_health_pct: number;
  total_shipments: number;
  delayed_shipments: number;
  delay_rate_pct: number;
  procurement_spend: number;
  open_purchase_orders: number;
  fraud_risk_returns: number;
  forecasted_demand_units: number;
  deltas: Record<string, number>;
}

export interface ForecastPoint {
  date: string;
  actual: number | null;
  actualRevenue?: number | null;
  forecast: number | null;
  forecastRevenue?: number | null;
  lower: number | null;
  lowerRevenue?: number | null;
  upper: number | null;
  upperRevenue?: number | null;
}

export interface ForecastRunResult {
  ran: boolean;
  products_processed?: number | null;
  batch_id?: string | null;
  reason?: string | null;
}

export const analyticsApi = {
  getDashboardSummary: () => api<DashboardSummary>("/api/v1/analytics/dashboard/summary"),
  getDashboardCharts: () => api<DashboardAnalyticsOut>("/api/v1/analytics/dashboard"),
  getForecastSeries: (params?: {
    product_id?: number;
    warehouse?: string;
    category?: string;
    period?: string;
  }) => {
    const q = new URLSearchParams();
    if (params?.product_id !== undefined) q.set("product_id", String(params.product_id));
    if (params?.warehouse) q.set("warehouse", params.warehouse);
    if (params?.category) q.set("category", params.category);
    if (params?.period) q.set("period", params.period);
    const query = q.toString();
    return api<ForecastPoint[]>(`/api/v1/analytics/forecast${query ? `?${query}` : ""}`);
  },
  getProductSalesTrend: (params: { product_id: number; warehouse_id?: number; limit?: number }) => {
    const query = new URLSearchParams();
    query.set("product_id", String(params.product_id));
    if (params.warehouse_id !== undefined) query.set("warehouse_id", String(params.warehouse_id));
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    return api<ProductSalesPoint[]>(`/api/v1/analytics/product-sales?${query}`);
  },
  runForecast: (force = true) =>
    api<ForecastRunResult>(`/api/v1/analytics/forecast/run?force=${force}`, {
      method: "POST",
    }),
  getLandingStats: () =>
    api<{
      totalRevenue: number;
      delayedShipments: number;
      totalReturns: number;
      insights: string[];
    }>("/api/v1/analytics/landing"),
};

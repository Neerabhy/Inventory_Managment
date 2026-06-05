import { api } from "./client";

export interface Shipment {
  id: number;
  shipment_code: string | null;
  direction: string;
  carrier: string | null;
  order_id: number | null;
  origin_city: string | null;
  destination_city: string | null;
  status: string;
  distance_km: number | null;
  total_weight_kg: number | null;
  fragile_items: boolean;
  weather_delay_flag: boolean;
  estimated_cost: number | null;
  actual_cost: number | null;
  expected_delivery_days: number | null;
  actual_delivery_days: number | null;
  delay_days: number | null;
  damage_reported: boolean;
}

export interface DelayAnalysis {
  total_shipments: number;
  delayed_count: number;
  delay_rate_pct: number;
  avg_delay_days: number;
  weather_delayed: number;
  damage_reported: number;
}

export interface ServiceableCity {
  id: number;
  city_name: string;
  state: string | null;
  is_active: boolean;
}

export interface InboundOrder {
  id: number;
  po_code: string | null;
  supplier_id: number;
  supplier_name: string;
  product_id: number;
  product_name: string;
  sku: string | null;
  warehouse_id: number;
  warehouse_city: string | null;
  quantity: number;
  unit_cost: number;
  total_amount: number;
  status: string | null;
  order_date: string;
  expected_delivery: string | null;
  actual_delivery: string | null;
  shipment_id: number | null;
  shipment_code: string | null;
  shipment_status: string | null;
  delivery_partner: string | null;
  origin_city: string | null;
  destination_city: string | null;
  shipping_cost: number | null;
  delay_days: number | null;
  has_shipment: boolean;
}

export interface LogisticsSummary {
  orders_placed: number;
  inbound_orders: number;
  outbound_orders: number;
  total_orders: number;
  delayed_shipments: number;
  delay_rate_pct: number;
}

export const logisticsApi = {
  listShipments: (params?: {
    direction?: string;
    status?: string;
    skip?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.direction) q.set("direction", params.direction);
    if (params?.status) q.set("status", params.status);
    if (params?.skip !== undefined) q.set("skip", String(params.skip));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return api<Shipment[]>(`/api/v1/logistics/shipments?${q}`);
  },

  getShipment: (id: number) => api<Shipment>(`/api/v1/logistics/shipments/${id}`),

  summary: () => api<LogisticsSummary>("/api/v1/logistics/summary"),

  listInboundOrders: (params?: { status?: string; include_closed?: boolean; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.include_closed !== undefined)
      q.set("include_closed", String(params.include_closed));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return api<InboundOrder[]>(`/api/v1/logistics/inbound-orders?${q}`);
  },

  delayAnalysis: () => api<DelayAnalysis>("/api/v1/logistics/delay-analysis"),

  listCities: () => api<ServiceableCity[]>("/api/v1/logistics/cities"),

  estimateCost: (payload: {
    distance_km: number;
    weight_kg: number;
    fragile_flag?: boolean;
    weather_delay_flag?: boolean;
  }) =>
    api<{
      estimated_cost_inr: number;
      delay_probability: number;
      confidence: number;
      model_used: string;
    }>("/api/v1/logistics/cost-estimate", { method: "POST", body: payload }),
};

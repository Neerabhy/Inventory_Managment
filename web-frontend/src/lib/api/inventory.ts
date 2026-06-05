import { api } from "./client";

// ── Types matching backend schemas ──────────────────────────────────
export interface Product {
  id: number;
  product_code: string | null;
  name: string;
  sku: string;
  category: string | null;
  brand: string | null;
  mrp: number | null;
  selling_price: number | null;
  manufacturing_cost: number | null;
  weight_kg: number | null;
  rating: number | null;
  review_count: number | null;
  warranty_months: number | null;
  return_rate?: number | null;
  defect_rate?: number | null;
  fragile_flag: boolean;
  battery_included: boolean;
  image_url: string | null;
  is_active: boolean;
  inventory_records?: InventoryRecord[];
}

export interface InventoryRecord {
  id: number;
  product_id: number;
  warehouse_id: number;
  quantity_on_hand: number;
  quantity_reserved?: number | null;
  quantity_in_transit?: number | null;
  available_quantity?: number | null;
  safety_stock: number | null;
  reorder_point: number | null;
  warehouse_city: string | null;
  inventory_turnover: number | null;
}

export interface InventoryOut {
  id: number;
  product_id: number;
  warehouse_id: number;
  quantity_on_hand: number;
  quantity_reserved?: number | null;
  quantity_in_transit?: number | null;
  available_quantity?: number | null;
  safety_stock: number | null;
  reorder_point: number | null;
  warehouse_city: string | null;
  inventory_turnover: number | null;
}

export interface AbcItem {
  product_id: number;
  product_name: string;
  product_code: string | null;
  total_revenue: number;
  revenue_pct: number;
  cumulative_pct: number;
  abc_class: "A" | "B" | "C";
}

export interface AbcAnalysisOut {
  items: AbcItem[];
  total_products: number;
  class_a_count: number;
  class_b_count: number;
  class_c_count: number;
}

export interface KpiDefinitionOut {
  id: number;
  kpi_code: string;
  kpi_name: string;
  description: string | null;
  formula: string | null;
  unit: string | null;
  warning_threshold: number | null;
  critical_threshold: number | null;
  higher_is_better: boolean;
  kpi_category: string;
}

export interface MovementOut {
  id: number;
  product_id: number;
  movement_type: string;
  quantity_delta: number;
  stock_before: number;
  stock_after: number;
  performed_by: string | null;
  note: string | null;
  created_at: string;
}

export interface StockAlert {
  product_id: number;
  product_name: string;
  sku: string;
  category: string | null;
  brand: string | null;
  image_url: string | null;
  selling_price: number | null;
  current_stock: number;
  safety_stock: number;
  reorder_point: number;
  warehouse_city: string | null;
  warehouse_id: number;
  incoming_qty: number;
  has_pending_order: boolean;
  pending_order_id: number | null;
  pending_order_qty: number | null;
  pending_order_value?: number | null;
}

// ── API functions ───────────────────────────────────────────────────
export const inventoryApi = {
  listProducts: (params?: {
    category?: string;
    search?: string;
    is_active?: boolean;
    skip?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set("category", params.category);
    if (params?.search) q.set("search", params.search);
    if (params?.is_active !== undefined) q.set("is_active", String(params.is_active));
    if (params?.skip !== undefined) q.set("skip", String(params.skip));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return api<Product[]>(`/api/v1/inventory/products?${q}`);
  },

  getProduct: (id: number) => api<Product>(`/api/v1/inventory/products/${id}`),

  getStockAlerts: () => api<StockAlert[]>("/api/v1/inventory/stock-alerts"),

  listStock: (params?: { below_reorder?: boolean; city?: string }) => {
    const q = new URLSearchParams();
    if (params?.below_reorder !== undefined) q.set("below_reorder", String(params.below_reorder));
    if (params?.city) q.set("city", params.city);
    return api<InventoryOut[]>(`/api/v1/inventory/stock?${q}`);
  },

  listMovements: (params?: {
    product_id?: number;
    movement_type?: string;
    skip?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.product_id) q.set("product_id", String(params.product_id));
    if (params?.movement_type) q.set("movement_type", params.movement_type);
    return api<MovementOut[]>(`/api/v1/inventory/movements?${q}`);
  },

  abcAnalysis: () => api<AbcAnalysisOut>("/api/v1/inventory/abc-analysis"),

  listKpis: (category?: string) => {
    const q = category ? `?category=${encodeURIComponent(category)}` : "";
    return api<KpiDefinitionOut[]>(`/api/v1/inventory/kpis${q}`);
  },
};

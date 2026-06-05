import { api } from "./client";

export interface Supplier {
  id: number;
  supplier_code: string | null;
  name: string;
  city: string | null;
  state: string | null;
  country: string | null;
  avg_lead_time_days: number | null;
  reliability_score: number | null;
  defect_rate: number | null;
  on_time_delivery_rate: number | null;
  avg_cost_index: number | null;
  payment_terms: string | null;
  minimum_order_qty: number | null;
  supplier_specialization: string | null;
  is_active: boolean;
}

export interface PurchaseOrder {
  id: number;
  po_code: string | null;
  supplier_id: number;
  product_id: number;
  delivery_city: string | null;
  quantity: number;
  unit_price: number | null;
  total_amount: number | null;
  status: string;
  expected_delivery_date: string | null;
  created_at: string;
}

export interface ProcurementDecision {
  id: number;
  po_id: number;
  decision: string;
  override_flag: boolean;
  override_reason: string | null;
  decided_at: string;
}

export interface VendorRankResult {
  supplier_id: number;
  supplier_name: string;
  composite_score: number;
  recommendation: string;
  label?: string;
  reliability_score: number | null;
  avg_lead_time_days: number | null;
  defect_rate: number | null;
  avg_cost_index: number | null;
  supplier_risk_label?: string | null;
  supplier_price?: number | null;
  lead_time_days?: number | null;
  supplier_city?: string | null;
  warehouse_city?: string | null;
  shipping_cost?: number | null;
  delivery_time_days?: number | null;
  landed_cost?: number | null;
  days_stock_covers?: number | null;
  avg_daily_demand?: number | null;
  rank_position?: number | null;
}

export interface SupplierProfile {
  supplier: Supplier;
  recent_orders: {
    id: number;
    po_code: string | null;
    product_id: number;
    product_name: string;
    sku: string | null;
    quantity: number;
    status: string;
    order_date: string | null;
    expected_delivery: string | null;
    unit_cost: number | null;
    total_amount: number | null;
    warehouse_id: number;
  }[];
  products_supplied: {
    product_id: number;
    product_name: string;
    sku: string;
    category: string | null;
    supplier_price: number | null;
    lead_time_days: number | null;
    preferred: boolean;
    contract_status: string | null;
  }[];
  stats: {
    total_orders: number;
    current_orders: number;
    avg_delivery_time_days: number | null;
    products_count: number;
    return_count: number;
    avg_product_rating: number | null;
  };
}

export const procurementApi = {
  listSuppliers: (params?: { is_active?: boolean; limit?: number; skip?: number }) => {
    const q = new URLSearchParams();
    if (params?.is_active !== undefined) q.set("is_active", String(params.is_active));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    if (params?.skip !== undefined) q.set("skip", String(params.skip));
    return api<Supplier[]>(`/api/v1/procurement/suppliers?${q}`);
  },

  getSupplier: (id: number) => api<Supplier>(`/api/v1/procurement/suppliers/${id}`),

  getSupplierProfile: (id: number) =>
    api<SupplierProfile>(`/api/v1/procurement/suppliers/${id}/profile`),

  rankVendors: (product_id: number, warehouse_id?: number) => {
    const q = new URLSearchParams();
    if (warehouse_id !== undefined) q.set("warehouse_id", String(warehouse_id));
    const query = q.toString();
    return api<VendorRankResult[]>(
      `/api/v1/procurement/suppliers/rank/${product_id}${query ? `?${query}` : ""}`,
    );
  },

  listOrders: (params?: {
    status?: string;
    supplier_id?: number;
    skip?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.supplier_id) q.set("supplier_id", String(params.supplier_id));
    if (params?.skip !== undefined) q.set("skip", String(params.skip));
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return api<PurchaseOrder[]>(`/api/v1/procurement/orders?${q}`);
  },

  getOrder: (id: number) => api<PurchaseOrder>(`/api/v1/procurement/orders/${id}`),

  listDecisions: () => api<ProcurementDecision[]>("/api/v1/procurement/decisions"),

  reorderProduct: (
    productId: number,
    supplierId: number,
    quantity: number,
    warehouseId: number,
  ) => {
    const q = new URLSearchParams({
      supplier_id: String(supplierId),
      warehouse_id: String(warehouseId),
      quantity: String(quantity),
    });
    return api<{ success: boolean; order_id: number; status: string; warehouse_id: number }>(
      `/api/v1/inventory/reorder/${productId}?${q}`,
      { method: "POST" },
    );
  },

  reorderAll: (supplierId: number, quantityPerProduct: number = 100) => {
    const q = new URLSearchParams({
      supplier_id: String(supplierId),
      quantity_per_product: String(quantityPerProduct),
    });
    return api<{ success: boolean; orders_created: number; product_ids: number[] }>(
      `/api/v1/inventory/reorder-all?${q}`,
      { method: "POST" },
    );
  },
};

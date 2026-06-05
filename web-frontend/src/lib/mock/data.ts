// Mock data layer - realistic enterprise data
export const CITIES = ["Delhi", "Mumbai", "Bangalore", "Jaipur", "Kolkata"] as const;
export type City = (typeof CITIES)[number];

export interface Product {
  product_id: string;
  sku: string;
  model_no: string;
  product_name: string;
  category: string;
  subcategory: string;
  brand: string;
  mrp: number;
  selling_price: number;
  manufacturing_cost: number;
  weight: number;
  rating: number;
  review_count: number;
  return_rate: number;
  defect_rate: number;
  warranty_months: number;
  fragile_flag: boolean;
  battery_included: boolean;
  image_url: string;
  launch_date: string;
  status: "active" | "discontinued" | "low_stock";
  current_stock: number;
  safety_stock: number;
  reorder_point: number;
  warehouse: City;
  inventory_turnover: number;
}

export interface Supplier {
  supplier_id: string;
  supplier_name: string;
  city: City;
  state: string;
  country: string;
  avg_lead_time_days: number;
  reliability_score: number;
  defect_rate: number;
  on_time_delivery_rate: number;
  avg_cost_index: number;
  payment_terms: string;
  minimum_order_qty: number;
  supplier_specialization: string;
}

export interface ReturnItem {
  return_id: string;
  sale_id: string;
  customer_id: string;
  product_id: string;
  product_name: string;
  customer_name: string;
  return_date: string;
  return_reason: string;
  return_type: "refund" | "replacement";
  days_after_delivery: number;
  product_condition: "new" | "used" | "damaged";
  refund_amount: number;
  reverse_logistics_cost: number;
  fraud_risk_score: number;
  approval_status: "pending" | "approved" | "declined";
  ai_recommendation: "approve" | "decline" | "manual_review";
  ai_confidence: number;
  ai_reason: string;
}

export interface Shipment {
  shipment_id: string;
  shipment_type: "inbound" | "outbound";
  logistics_provider: string;
  source_city: City;
  destination_city: City;
  distance_km: number;
  transportation_mode: "road" | "air" | "rail";
  shipping_cost: number;
  expected_delivery_days: number;
  actual_delivery_days: number;
  delayed_flag: boolean;
  weather_delay_flag: boolean;
  remote_area_flag: boolean;
  shipment_status: "in_transit" | "delivered" | "delayed" | "pending";
  eta_progress: number;
}

const seed = (n: number) => {
  let s = n;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
};
const rnd = seed(42);
const pick = <T,>(a: readonly T[]) => a[Math.floor(rnd() * a.length)];
const num = (a: number, b: number) => Math.round(a + rnd() * (b - a));

const PRODUCT_IMG: Record<string, string> = {
  Laptops: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400",
  Smartphones: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400",
  Headphones: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400",
  Monitors: "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400",
  Tablets: "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=400",
  Cameras: "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=400",
  Speakers: "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=400",
  Wearables: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400",
};

const CATEGORIES = Object.keys(PRODUCT_IMG);
const BRANDS = ["Acer", "Sony", "Samsung", "Apple", "Dell", "HP", "Lenovo", "Bose", "JBL", "Canon"];

export const products: Product[] = Array.from({ length: 48 }, (_, i) => {
  const category = pick(CATEGORIES);
  const brand = pick(BRANDS);
  const mrp = num(8000, 120000);
  const stock = num(0, 800);
  const safety = num(40, 120);
  return {
    product_id: `P-${String(i + 1).padStart(4, "0")}`,
    sku: `${brand.slice(0, 3).toUpperCase()}-${category.slice(0, 3).toUpperCase()}-${1000 + i}`,
    model_no: `${brand.slice(0, 2).toUpperCase()}${num(100, 999)}X`,
    product_name: `${brand} ${category.slice(0, -1)} ${pick(["Pro", "Air", "Max", "Lite", "Edge", "Ultra"])} ${num(2024, 2026)}`,
    category,
    subcategory: pick(["Premium", "Mid-range", "Entry"]),
    brand,
    mrp,
    selling_price: Math.round(mrp * (0.78 + rnd() * 0.18)),
    manufacturing_cost: Math.round(mrp * (0.45 + rnd() * 0.15)),
    weight: +(0.3 + rnd() * 3.2).toFixed(2),
    rating: +(3.5 + rnd() * 1.4).toFixed(1),
    review_count: num(20, 5400),
    return_rate: +(rnd() * 0.18).toFixed(3),
    defect_rate: +(rnd() * 0.06).toFixed(3),
    warranty_months: pick([6, 12, 18, 24]),
    fragile_flag: rnd() > 0.7,
    battery_included: rnd() > 0.4,
    image_url: PRODUCT_IMG[category],
    launch_date: `2024-${String(num(1, 12)).padStart(2, "0")}-15`,
    status: stock < safety ? "low_stock" : rnd() > 0.95 ? "discontinued" : "active",
    current_stock: stock,
    safety_stock: safety,
    reorder_point: safety + num(20, 60),
    warehouse: pick(CITIES),
    inventory_turnover: +(2 + rnd() * 8).toFixed(2),
  };
});

const SUPPLIER_NAMES = [
  "Bharat Electronics Ltd",
  "Quantum Components Pvt",
  "NovaTech Distributors",
  "Apex Hardware Co",
  "Stellar Imports",
  "Meridian Supply",
  "Vector Trading",
  "Pinnacle Logistics",
  "Orion Electronics",
  "Zenith Sourcing",
];

export const suppliers: Supplier[] = SUPPLIER_NAMES.map((name, i) => ({
  supplier_id: `S-${String(i + 1).padStart(3, "0")}`,
  supplier_name: name,
  city: pick(CITIES),
  state: pick(["Delhi", "Maharashtra", "Karnataka", "Rajasthan", "West Bengal"]),
  country: "India",
  avg_lead_time_days: num(3, 18),
  reliability_score: +(0.7 + rnd() * 0.3).toFixed(2),
  defect_rate: +(rnd() * 0.05).toFixed(3),
  on_time_delivery_rate: +(0.78 + rnd() * 0.2).toFixed(2),
  avg_cost_index: +(0.85 + rnd() * 0.3).toFixed(2),
  payment_terms: pick(["Net 15", "Net 30", "Net 45", "Net 60"]),
  minimum_order_qty: num(10, 200),
  supplier_specialization: pick(CATEGORIES),
}));

const REASONS = [
  "Damaged in transit",
  "Wrong item delivered",
  "Defective product",
  "Not as described",
  "Better price found",
  "No longer needed",
  "Quality issue",
];

export const returns: ReturnItem[] = Array.from({ length: 32 }, (_, i) => {
  const p = products[num(0, products.length - 1)];
  const fraud = +(rnd()).toFixed(2);
  const cost = num(80, 1800);
  const refund = num(2000, 45000);
  const ai_rec = fraud > 0.7 ? "decline" : cost > 1200 || fraud > 0.45 ? "manual_review" : "approve";
  return {
    return_id: `R-${String(i + 1).padStart(5, "0")}`,
    sale_id: `O-${num(10000, 99999)}`,
    customer_id: `C-${num(1000, 9999)}`,
    product_id: p.product_id,
    product_name: p.product_name,
    customer_name: pick(["Aarav Sharma", "Priya Patel", "Rohan Singh", "Anita Desai", "Vikram Iyer", "Neha Kapoor", "Arjun Mehta", "Sneha Reddy"]),
    return_date: `2026-05-${String(num(1, 16)).padStart(2, "0")}`,
    return_reason: pick(REASONS),
    return_type: rnd() > 0.5 ? "refund" : "replacement",
    days_after_delivery: num(1, 14),
    product_condition: pick(["new", "used", "damaged"]),
    refund_amount: refund,
    reverse_logistics_cost: cost,
    fraud_risk_score: fraud,
    approval_status: "pending",
    ai_recommendation: ai_rec,
    ai_confidence: +(0.7 + rnd() * 0.3).toFixed(2),
    ai_reason:
      ai_rec === "approve"
        ? "Low fraud score, customer in good standing, condition matches policy."
        : ai_rec === "decline"
          ? "Elevated fraud signals, customer return ratio above threshold."
          : "Reverse logistics cost exceeds 15% of refund value — manual review suggested.",
  };
});

export const shipments: Shipment[] = Array.from({ length: 28 }, (_, i) => {
  const type = rnd() > 0.5 ? "inbound" : "outbound";
  const src = pick(CITIES);
  let dst = pick(CITIES);
  while (dst === src) dst = pick(CITIES);
  const exp = num(2, 9);
  const act = exp + (rnd() > 0.65 ? num(1, 5) : 0);
  return {
    shipment_id: `SHP-${String(i + 1).padStart(5, "0")}`,
    shipment_type: type,
    logistics_provider: pick(["BlueDart", "Delhivery", "Ecom Express", "DHL", "FedEx"]),
    source_city: src,
    destination_city: dst,
    distance_km: num(150, 2400),
    transportation_mode: pick(["road", "air", "rail"]),
    shipping_cost: num(800, 18000),
    expected_delivery_days: exp,
    actual_delivery_days: act,
    delayed_flag: act > exp,
    weather_delay_flag: rnd() > 0.85,
    remote_area_flag: rnd() > 0.8,
    shipment_status: rnd() > 0.6 ? "in_transit" : act > exp ? "delayed" : "delivered",
    eta_progress: Math.round(rnd() * 100),
  };
});

// Time series
export const revenueTrend = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  revenue: 240000 + Math.sin(i / 4) * 60000 + i * 4500 + Math.random() * 30000,
  orders: 320 + Math.cos(i / 5) * 60 + i * 4 + Math.random() * 40,
}));

export const forecastSeries = Array.from({ length: 24 }, (_, i) => {
  const actual = i < 16 ? 1200 + Math.sin(i / 3) * 220 + i * 35 : null;
  const forecast = i >= 14 ? 1480 + Math.sin(i / 3) * 250 + i * 38 : null;
  const upper = forecast ? forecast * 1.18 : null;
  const lower = forecast ? forecast * 0.82 : null;
  return { week: `W${i + 1}`, actual, forecast, upper, lower };
});

export const categoryPerf = CATEGORIES.map((c) => ({
  category: c,
  revenue: num(120000, 880000),
  units: num(180, 1400),
}));

export const returnReasons = REASONS.map((r) => ({ reason: r, count: num(8, 64) }));

export const shipmentDelayBuckets = [
  { bucket: "On-time", value: 312 },
  { bucket: "1-2 days late", value: 84 },
  { bucket: "3-5 days late", value: 31 },
  { bucket: ">5 days late", value: 9 },
];

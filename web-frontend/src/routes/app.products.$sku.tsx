import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowLeft, Star, Sparkles, Award, Zap, IndianRupee, Loader2, ShoppingCart } from "lucide-react";

import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { analyticsApi } from "@/lib/api/analytics";
import { copilotApi } from "@/lib/api/copilot";
import { ProductImage } from "@/components/product/ProductImage";
import { inventoryApi, type InventoryRecord, type Product } from "@/lib/api/inventory";
import { procurementApi } from "@/lib/api/procurement";

export const Route = createFileRoute("/app/products/$sku")({
  head: ({ params }) => ({ meta: [{ title: `${params.sku} - Product detail` }] }),
  component: Detail,
  loader: async ({ params }) => {
    const res = await inventoryApi.listProducts({ search: params.sku });
    const p = res.find((x: Product) => x.sku === params.sku);
    if (!p) throw notFound();
    return { product: p };
  },
  notFoundComponent: () => <div className="p-8">Product not found.</div>,
});

type StockSummary = {
  label: string;
  quantity_on_hand: number;
  quantity_reserved: number;
  available_quantity: number;
  incoming_quantity: number;
  safety_stock: number;
  reorder_point: number;
  inventory_turnover: number | null;
};

function Detail() {
  const { product: p } = Route.useLoaderData() as { product: Product };
  const [warehouseValue, setWarehouseValue] = useState("all");
  const [poOpen, setPoOpen] = useState(false);
  const [poVendorId, setPoVendorId] = useState("");
  const [poWarehouseValue, setPoWarehouseValue] = useState("");
  const [poQty, setPoQty] = useState("100");
  const [isPlacingPo, setIsPlacingPo] = useState(false);

  const warehouseId = warehouseValue === "all" ? undefined : Number(warehouseValue);
  const inventoryRecords = useMemo(() => p.inventory_records ?? [], [p.inventory_records]);
  const stockSummary = useMemo(
    () => summarizeStock(inventoryRecords, warehouseId),
    [inventoryRecords, warehouseId],
  );
  const defaultPoRecord = useMemo(
    () => pickPoWarehouse(inventoryRecords, warehouseId),
    [inventoryRecords, warehouseId],
  );
  const poWarehouseId = Number(poWarehouseValue || defaultPoRecord?.warehouse_id || 0);
  const poRecord =
    inventoryRecords.find((record) => record.warehouse_id === poWarehouseId) ?? defaultPoRecord;
  const suggestedPoQty = Math.max(
    (poRecord?.reorder_point ?? stockSummary.reorder_point) -
      (poRecord?.quantity_on_hand ?? stockSummary.quantity_on_hand),
    100,
  );

  const { data: rankedVendors = [] } = useApi(
    () => procurementApi.rankVendors(p.id, warehouseId),
    [p.id, warehouseId],
  );
  const { data: salesTrend = [] } = useApi(
    () =>
      analyticsApi.getProductSalesTrend({ product_id: p.id, warehouse_id: warehouseId, limit: 30 }),
    [p.id, warehouseId],
  );
  const { data: forecastSeries = [] } = useApi(
    () => analyticsApi.getForecastSeries({ product_id: p.id, period: "weeks" }),
    [p.id],
  );
  const { data: productInsights } = useApi(
    () => copilotApi.getProductInsights(p.sku, warehouseId),
    [p.sku, warehouseId],
  );
  const soldUnits = salesTrend.reduce((sum, point) => sum + (point.units ?? 0), 0);
  const salesRevenue = salesTrend.reduce((sum, point) => sum + (point.revenue ?? 0), 0);
  const forecastDemand = forecastSeries.reduce((sum, point) => sum + (point.forecast ?? 0), 0);

  const linked = rankedVendors.slice(0, 3).map((s, i) => ({
    ...s,
    landed_cost:
      s.landed_cost ?? (p.manufacturing_cost ? p.manufacturing_cost * (s.avg_cost_index ?? 0) : 0),
    ai_score: s.composite_score,
    badge: i === 0 ? "BEST CHOICE" : i === 1 ? "FASTEST DELIVERY" : "LOWEST COST",
    badgeColor:
      i === 0
        ? "bg-primary text-primary-foreground"
        : i === 1
          ? "bg-success text-success-foreground"
          : "bg-info text-info-foreground",
    badgeIcon: i === 0 ? Award : i === 1 ? Zap : IndianRupee,
  }));
  const selectedPoVendor = rankedVendors.find((s) => String(s.supplier_id) === poVendorId);
  const selectedPoUnitCost =
    selectedPoVendor?.landed_cost ??
    selectedPoVendor?.supplier_price ??
    selectedPoVendor?.avg_cost_index ??
    p.manufacturing_cost ??
    0;
  const selectedPoTotal = Math.max(0, Number(poQty) || 0) * selectedPoUnitCost;

  const openPoDialog = (supplierId: number) => {
    setPoVendorId(String(supplierId));
    setPoWarehouseValue(String(defaultPoRecord?.warehouse_id ?? ""));
    setPoQty(String(suggestedPoQty));
    setPoOpen(true);
  };

  const handlePlacePo = async () => {
    if (!poVendorId || !poWarehouseId) return;
    setIsPlacingPo(true);
    try {
      const qty = Math.max(1, Number(poQty) || suggestedPoQty);
      await procurementApi.reorderProduct(p.id, Number(poVendorId), qty, poWarehouseId);
      const warehouseLabel =
        poRecord?.warehouse_city ?? (poWarehouseId ? `WH-${poWarehouseId}` : "selected warehouse");
      toast.success(`PO created for ${p.name} at ${warehouseLabel} - ${qty} units on the way.`);
      setPoOpen(false);
    } catch (error: unknown) {
      toast.error(`Failed to place PO: ${errorMessage(error)}`);
    } finally {
      setIsPlacingPo(false);
    }
  };

  return (
    <>
      <Button variant="ghost" size="sm" asChild className="-ml-2 mb-3">
        <Link to="/app/products">
          <ArrowLeft className="mr-1 h-4 w-4" /> Catalog
        </Link>
      </Button>
      <PageHeader
        title={p.name}
        subtitle={`${p.brand ?? "-"} · ${p.category ?? "-"} · SKU ${p.sku}`}
        actions={
          <Select value={warehouseValue} onValueChange={setWarehouseValue}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Warehouse" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All warehouses</SelectItem>
              {inventoryRecords.map((record) => (
                <SelectItem key={record.warehouse_id} value={String(record.warehouse_id)}>
                  {record.warehouse_city ?? `WH-${record.warehouse_id}`} (WH-{record.warehouse_id})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SectionCard className="lg:col-span-1">
          <div className="aspect-square overflow-hidden rounded-xl border border-border bg-white p-5 shadow-inner">
            <ProductImage
              src={p.image_url}
              category={p.category}
              alt={p.name}
              className="h-full w-full object-contain"
            />
          </div>
          <div className="mt-3 rounded-lg border border-border bg-muted/30 px-3 py-2">
            <div className="truncate text-xs font-medium text-foreground">{p.name}</div>
            <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
              {p.brand ?? "Brand"} · {p.category ?? "Category"}
            </div>
          </div>
        </SectionCard>

        <div className="space-y-4 lg:col-span-2">
          <SectionCard>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="text-3xl font-semibold tracking-tight tabular-nums">
                  ₹{(p.selling_price ?? 0).toLocaleString()}
                </div>
                <div className="text-sm text-muted-foreground line-through tabular-nums">
                  ₹{(p.mrp ?? 0).toLocaleString()}
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1 text-sm">
                    <Star className="h-4 w-4 fill-warning text-warning" />
                    {p.rating}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {(p.review_count ?? 0).toLocaleString()} reviews
                  </span>
                  <Badge variant="secondary">{stockSummary.label}</Badge>
                </div>
              </div>
              <div className="shrink-0 rounded-lg border border-border bg-muted/20 px-4 py-3 text-left sm:text-right">
                <div className="text-xs text-muted-foreground">Current stock</div>
                <div className="text-2xl font-semibold tabular-nums">
                  {stockSummary.quantity_on_hand.toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground">
                  Safety {stockSummary.safety_stock.toLocaleString()} · Reorder{" "}
                  {stockSummary.reorder_point.toLocaleString()}
                </div>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[
                ["Available stock", stockSummary.available_quantity.toLocaleString()],
                ["Reserved stock", stockSummary.quantity_reserved.toLocaleString()],
                ["Incoming stock", stockSummary.incoming_quantity.toLocaleString()],
                ["Units sold", soldUnits.toLocaleString()],
                ["Sales revenue", `Rs ${Math.round(salesRevenue).toLocaleString()}`],
                ["Forecast demand", Math.round(forecastDemand).toLocaleString()],
                ["Return rate", `${((p.return_rate ?? 0) * 100).toFixed(1)}%`],
                ["Rating", `${(p.rating ?? 0).toFixed(1)} / 5`],
                ["Reviews", (p.review_count ?? 0).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-border p-3">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {k}
                  </div>
                  <div className="mt-1 break-words text-base font-semibold tabular-nums">{v}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title="AI recommendations"
            actions={<Sparkles className="h-4 w-4 text-primary" />}
          >
            <ul className="space-y-2 text-sm">
              {(
                productInsights?.insights ?? [
                  "Review safety stock against current demand.",
                  "Use the highest-ranked supplier when lead time and cost are both acceptable.",
                  "Monitor defect and return rates before expanding procurement volume.",
                ]
              ).map((insight) => (
                <li key={insight} className="flex gap-2 leading-relaxed">
                  <span className="text-primary">•</span> {cleanRecommendation(insight)}
                </li>
              ))}
            </ul>
          </SectionCard>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Sales trend" subtitle={`Last 30 days · ${stockSummary.label}`}>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={salesTrend}>
                <defs>
                  <linearGradient id="pdSales" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                  vertical={false}
                />
                <XAxis dataKey="day" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="var(--color-chart-1)"
                  strokeWidth={2}
                  fill="url(#pdSales)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard title="Forecast" subtitle="Next 8 weeks">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastSeries}>
                <CartesianGrid
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                  vertical={false}
                />
                <XAxis dataKey="date" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Line dataKey="actual" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
                <Line
                  dataKey="forecast"
                  stroke="var(--color-chart-3)"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="Supplier comparison"
        subtitle="Multiple suppliers ranked by AI"
        actions={<Badge variant="secondary">{linked.length} active</Badge>}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {linked.map((s, i) => {
            const Icon = s.badgeIcon;
            return (
              <motion.div
                key={s.supplier_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`relative rounded-2xl border p-5 transition-all hover:shadow-elevated ${
                  i === 0
                    ? "border-primary/40 bg-gradient-to-br from-primary/8 to-transparent"
                    : "border-border bg-card"
                }`}
              >
                <div
                  className={`mb-3 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${s.badgeColor}`}
                >
                  <Icon className="h-3 w-3" /> {s.badge}
                </div>
                <div className="font-semibold">{s.supplier_name}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
                <div className="mt-4 space-y-2 text-sm">
                  <Row k="Reliability" v={`${((s.reliability_score ?? 0) * 100).toFixed(0)}%`} />
                  <Row k="Ship from" v={s.supplier_city ?? "N/A"} />
                  <Row
                    k="Avg delivery"
                    v={`${s.delivery_time_days ?? s.avg_lead_time_days ?? 0}d`}
                  />
                  <Row k="Defect rate" v={`${((s.defect_rate ?? 0) * 100).toFixed(2)}%`} />
                  <Row k="Ship cost" v={`Rs ${(s.shipping_cost ?? 0).toLocaleString()}`} />
                  <Row
                    k="Landed cost"
                    v={`Rs ${(s.landed_cost ?? s.supplier_price ?? 0).toLocaleString()}`}
                  />
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                  <div>
                    <div className="text-[10px] text-muted-foreground">AI score</div>
                    <div className="text-lg font-semibold text-primary">
                      {(s.ai_score * 100).toFixed(0)}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant={i === 0 ? "default" : "outline"}
                    className={i === 0 ? "gradient-primary border-0 text-primary-foreground" : ""}
                    onClick={() => openPoDialog(s.supplier_id)}
                  >
                    <ShoppingCart className="mr-1.5 h-3.5 w-3.5" />
                    Place PO
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>
      </SectionCard>

      <Dialog open={poOpen} onOpenChange={setPoOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Place purchase order</DialogTitle>
            <DialogDescription>
              Create a purchase order for {p.name} using the selected supplier recommendation.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Supplier</Label>
              <Select value={poVendorId} onValueChange={setPoVendorId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select supplier" />
                </SelectTrigger>
                <SelectContent>
                  {rankedVendors.map((vendor) => (
                    <SelectItem key={vendor.supplier_id} value={String(vendor.supplier_id)}>
                      {vendor.supplier_name} - score{" "}
                      {Math.round((vendor.composite_score ?? 0) * 100)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Warehouse</Label>
              <Select value={poWarehouseValue} onValueChange={setPoWarehouseValue}>
                <SelectTrigger>
                  <SelectValue placeholder="Select warehouse" />
                </SelectTrigger>
                <SelectContent>
                  {inventoryRecords.map((record) => (
                    <SelectItem key={record.warehouse_id} value={String(record.warehouse_id)}>
                      {record.warehouse_city ?? `WH-${record.warehouse_id}`} - stock{" "}
                      {(record.quantity_on_hand ?? 0).toLocaleString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Quantity to order</Label>
              <Input type="number" value={poQty} onChange={(event) => setPoQty(event.target.value)} />
              <p className="text-xs text-muted-foreground">
                Suggested: {suggestedPoQty.toLocaleString()} units
              </p>
            </div>

            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Estimated order value</span>
                <span className="font-semibold tabular-nums">{formatCurrency(selectedPoTotal)}</span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {(Number(poQty) || 0).toLocaleString()} units x{" "}
                {formatCurrency(selectedPoUnitCost)} selected vendor cost
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPoOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handlePlacePo}
              disabled={!poVendorId || !poWarehouseId || isPlacingPo}
              className="gradient-primary border-0 text-primary-foreground"
            >
              {isPlacingPo && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Submit Order
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function summarizeStock(records: InventoryRecord[], warehouseId?: number): StockSummary {
  const selected =
    warehouseId === undefined
      ? records
      : records.filter((record) => record.warehouse_id === warehouseId);
  const usable = selected.length > 0 ? selected : records;
  const turnoverValues = usable
    .map((record) => record.inventory_turnover)
    .filter((value): value is number => value != null);
  const label =
    warehouseId === undefined
      ? "All warehouses"
      : (usable[0]?.warehouse_city ?? `WH-${warehouseId}`);

  return {
    label,
    quantity_on_hand: usable.reduce((sum, record) => sum + (record.quantity_on_hand ?? 0), 0),
    quantity_reserved: usable.reduce((sum, record) => sum + (record.quantity_reserved ?? 0), 0),
    available_quantity: usable.reduce(
      (sum, record) => sum + (record.available_quantity ?? record.quantity_on_hand ?? 0),
      0,
    ),
    incoming_quantity: usable.reduce((sum, record) => sum + (record.quantity_in_transit ?? 0), 0),
    safety_stock: usable.reduce((sum, record) => sum + (record.safety_stock ?? 0), 0),
    reorder_point: usable.reduce((sum, record) => sum + (record.reorder_point ?? 0), 0),
    inventory_turnover:
      turnoverValues.length > 0
        ? turnoverValues.reduce((sum, value) => sum + value, 0) / turnoverValues.length
        : null,
  };
}

function pickPoWarehouse(records: InventoryRecord[], warehouseId?: number) {
  if (records.length === 0) return undefined;
  if (warehouseId !== undefined) {
    return records.find((record) => record.warehouse_id === warehouseId) ?? records[0];
  }
  return [...records].sort(
    (a, b) =>
      (a.available_quantity ?? a.quantity_on_hand ?? Number.MAX_SAFE_INTEGER) -
      (b.available_quantity ?? b.quantity_on_hand ?? Number.MAX_SAFE_INTEGER),
  )[0];
}

function formatCurrency(value: number | null | undefined) {
  if (value == null) return "N/A";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown error";
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium tabular-nums">{v}</span>
    </div>
  );
}

function cleanRecommendation(value: string) {
  return value
    .replace(/\*\*/g, "")
    .replace(/^\s*[-*]\s+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

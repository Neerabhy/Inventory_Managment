import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState, useEffect } from "react";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  Filter,
  Boxes,
  Loader2,
  ShoppingCart,
  PackageCheck,
  AlertTriangle,
  TruckIcon,
  ArrowUpDown,
  ExternalLink,
  Clock,
  IndianRupee,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { useApi } from "@/hooks/useApi";
import { inventoryApi, type StockAlert } from "@/lib/api/inventory";
import { procurementApi, type VendorRankResult } from "@/lib/api/procurement";
import { ProductImage } from "@/components/product/ProductImage";

const CITIES = ["Delhi", "Mumbai", "Bangalore", "Jaipur", "Kolkata"];

export const Route = createFileRoute("/app/inventory")({
  head: () => ({ meta: [{ title: "Inventory Management — AI Inventory Copilot" }] }),
  component: Inventory,
});

function StockBar({
  current,
  safety,
  reorder,
}: {
  current: number;
  safety: number;
  reorder: number;
}) {
  const max = Math.max(reorder * 1.5, 1);
  const pct = Math.min(100, (current / max) * 100);
  const color =
    current <= safety ? "bg-destructive" : current <= reorder ? "bg-warning" : "bg-success";
  return (
    <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden mt-1">
      <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function formatCurrency(value: number | null | undefined) {
  if (value == null) return "N/A";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatScore(value: number | null | undefined) {
  if (value == null) return "N/A";
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}/100`;
}

function formatDays(value: number | null | undefined) {
  if (value == null || value <= 0) return "N/A";
  return `${value}d`;
}

function formatPct(value: number | null | undefined) {
  if (value == null) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}

function vendorLabel(vendor: VendorRankResult) {
  return vendor.recommendation || vendor.label || "RECOMMENDED";
}

function vendorReason(vendor: VendorRankResult) {
  const rank = vendor.rank_position ?? 0;
  const score = formatScore(vendor.composite_score);
  const delivery = formatDays(
    vendor.delivery_time_days ?? vendor.lead_time_days ?? vendor.avg_lead_time_days,
  );
  const cost = formatCurrency(vendor.landed_cost ?? vendor.supplier_price ?? vendor.avg_cost_index);
  if (rank === 1) {
    return `Rank #1 because it has the strongest score (${score}) with ${delivery} delivery and ${cost} landed cost.`;
  }
  return `Rank #${rank || "-"} because its score (${score}), ${delivery} delivery, or ${cost} cost trails higher-ranked vendors.`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown error";
}

function VendorFact({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone?: "good" | "bad";
}) {
  return (
    <div className="rounded-md border border-border bg-card/70 p-2">
      <div className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div
        className={`mt-1 truncate text-xs font-semibold tabular-nums ${
          tone === "bad" ? "text-destructive" : tone === "good" ? "text-success" : "text-foreground"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function VendorOptionCard({
  vendor,
  selected,
  onSelect,
}: {
  vendor: VendorRankResult;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border p-3 text-left transition-all ${
        selected
          ? "border-primary bg-primary/8 shadow-card"
          : "border-border bg-background hover:border-primary/40 hover:bg-muted/30"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{vendor.supplier_name}</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge
              variant={vendorLabel(vendor) === "HIGH RISK" ? "destructive" : "secondary"}
              className="text-[10px]"
            >
              {vendorLabel(vendor)}
            </Badge>
            <Badge variant="outline" className="text-[10px]">
              Rank #{vendor.rank_position ?? "-"}
            </Badge>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">AI score</div>
          <div className="text-sm font-semibold tabular-nums">
            {formatScore(vendor.composite_score)}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <VendorFact
          icon={Clock}
          label="Delivery"
          value={formatDays(vendor.lead_time_days ?? vendor.avg_lead_time_days)}
        />
        <VendorFact
          icon={IndianRupee}
          label="Unit cost"
          value={formatCurrency(vendor.supplier_price ?? vendor.avg_cost_index)}
        />
        <VendorFact
          icon={TruckIcon}
          label="Ship cost"
          value={formatCurrency(vendor.shipping_cost)}
        />
        <VendorFact
          icon={PackageCheck}
          label="Landed"
          value={formatCurrency(vendor.landed_cost ?? vendor.supplier_price)}
        />
        <VendorFact
          icon={AlertTriangle}
          label="Defects"
          value={formatPct(vendor.defect_rate)}
          tone={(vendor.defect_rate ?? 0) <= 2 ? "good" : "bad"}
        />
      </div>
      <div className="mt-2 text-xs text-muted-foreground">{vendorReason(vendor)}</div>
    </button>
  );
}

function MiniKpi({
  label,
  value,
  description,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: "destructive" | "warning" | "info";
}) {
  const accentClass = {
    destructive: "bg-destructive/10 text-destructive border-destructive/20",
    warning: "bg-warning/10 text-warning border-warning/20",
    info: "bg-info/10 text-info border-info/20",
  }[accent];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="group rounded-2xl border border-border bg-card p-4 flex items-center gap-3 shadow-card transition hover:shadow-elevated">
          <div className={`w-9 h-9 rounded-xl border grid place-items-center ${accentClass}`}>
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{label}</div>
            <div
              className={`text-xl font-semibold ${accent === "info" ? "text-info" : accent === "warning" ? "text-warning" : "text-destructive"}`}
            >
              {value}
            </div>
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs border-border bg-popover text-popover-foreground shadow-elevated">
        <div className="font-semibold">{label}</div>
        <div className="mt-1 text-xs text-muted-foreground">{description}</div>
      </TooltipContent>
    </Tooltip>
  );
}

const TABLE_HEAD = (
  <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
    <th className="px-4 py-3 font-medium">Product</th>
    <th className="px-4 py-3 font-medium">SKU</th>
    <th className="px-4 py-3 font-medium">Warehouse</th>
    <th className="px-4 py-3 font-medium text-right">
      <span className="inline-flex items-center gap-1">
        Stock <ArrowUpDown className="w-3 h-3" />
      </span>
    </th>
    <th className="px-4 py-3 font-medium">On the Way</th>
    <th className="px-4 py-3 font-medium">Safety / Reorder</th>
    <th className="px-4 py-3 font-medium">Status</th>
    <th className="px-4 py-3 font-medium text-right">Actions</th>
  </tr>
);

function AlertRow({
  alert,
  idx,
  onReorder,
}: {
  alert: StockAlert;
  idx: number;
  onReorder: (a: StockAlert) => void;
}) {
  const isCritical = alert.current_stock <= alert.safety_stock;
  return (
    <motion.tr
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.02 }}
      className="border-t border-border hover:bg-muted/30 transition group"
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <ProductImage
            src={alert.image_url}
            category={alert.category}
            alt={alert.product_name}
            className="w-10 h-10 rounded-lg object-cover border border-border bg-muted"
          />
          <div className="min-w-0">
            <div className="font-medium truncate max-w-[180px]">{alert.product_name}</div>
            <div className="text-xs text-muted-foreground">
              {alert.brand} · {alert.category}
            </div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 font-mono text-xs">{alert.sku}</td>
      <td className="px-4 py-3 text-xs text-muted-foreground">{alert.warehouse_city}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        <div className={`font-semibold ${isCritical ? "text-destructive" : "text-warning"}`}>
          {alert.current_stock}
        </div>
        <StockBar
          current={alert.current_stock}
          safety={alert.safety_stock}
          reorder={alert.reorder_point}
        />
      </td>
      <td className="px-4 py-3">
        {alert.incoming_qty > 0 ? (
          <div className="flex items-center gap-1.5 text-info text-sm font-medium">
            <TruckIcon className="w-3.5 h-3.5" />
            {alert.incoming_qty}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {alert.safety_stock} / {alert.reorder_point}
      </td>
      <td className="px-4 py-3">
        {isCritical ? (
          <Badge variant="destructive">Critical</Badge>
        ) : (
          <Badge className="bg-warning text-warning-foreground hover:bg-warning/90">Reorder</Badge>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition">
          {!alert.has_pending_order && (
            <Button size="sm" variant="outline" onClick={() => onReorder(alert)}>
              <ShoppingCart className="w-3.5 h-3.5 mr-1" /> Reorder
            </Button>
          )}
          <Button asChild size="sm" variant="ghost">
            <Link to="/app/products/$sku" params={{ sku: alert.sku }}>
              <ExternalLink className="w-3.5 h-3.5 mr-1" /> View
            </Link>
          </Button>
        </div>
      </td>
    </motion.tr>
  );
}

function OrderedRow({ alert, idx }: { alert: StockAlert; idx: number }) {
  return (
    <motion.tr
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.02 }}
      className="border-t border-border hover:bg-muted/30 transition group"
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <ProductImage
            src={alert.image_url}
            category={alert.category}
            alt={alert.product_name}
            className="w-10 h-10 rounded-lg object-cover border border-border bg-muted"
          />
          <div className="min-w-0">
            <div className="font-medium truncate max-w-[180px]">{alert.product_name}</div>
            <div className="text-xs text-muted-foreground">
              {alert.brand} · {alert.category}
            </div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 font-mono text-xs">{alert.sku}</td>
      <td className="px-4 py-3 text-xs text-muted-foreground">{alert.warehouse_city}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        <div className="font-medium">{alert.current_stock}</div>
        <StockBar
          current={alert.current_stock}
          safety={alert.safety_stock}
          reorder={alert.reorder_point}
        />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5 text-info font-medium text-sm">
          <TruckIcon className="w-3.5 h-3.5" />
          {alert.incoming_qty} on the way
        </div>
        {alert.pending_order_id && (
          <div className="text-xs text-muted-foreground mt-0.5">PO #{alert.pending_order_id}</div>
        )}
        {alert.pending_order_value != null && alert.pending_order_value > 0 && (
          <div className="text-xs text-muted-foreground mt-0.5">
            Value {formatCurrency(alert.pending_order_value)}
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {alert.safety_stock} / {alert.reorder_point}
      </td>
      <td className="px-4 py-3">
        <Badge className="bg-info/10 text-info border border-info/20 gap-1">
          <PackageCheck className="w-3 h-3" /> Ordered
        </Badge>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition">
          <Button asChild size="sm" variant="ghost">
            <Link to="/app/products/$sku" params={{ sku: alert.sku }}>
              <ExternalLink className="w-3.5 h-3.5 mr-1" /> View
            </Link>
          </Button>
        </div>
      </td>
    </motion.tr>
  );
}

function Inventory() {
  const [q, setQ] = useState("");
  const [wh, setWh] = useState("all");
  const [cat, setCat] = useState("all");

  // Individual reorder modal
  const [reorderAlert, setReorderAlert] = useState<StockAlert | null>(null);
  const [rankedVendors, setRankedVendors] = useState<VendorRankResult[]>([]);
  const [selectedVendorId, setSelectedVendorId] = useState("");
  const [reorderQty, setReorderQty] = useState("100");
  const [isReordering, setIsReordering] = useState(false);

  // Reorder All modal
  const [reorderAllOpen, setReorderAllOpen] = useState(false);
  const [allVendors, setAllVendors] = useState<VendorRankResult[]>([]);
  const [allVendorId, setAllVendorId] = useState("");
  const [allQty, setAllQty] = useState("100");
  const [isReorderingAll, setIsReorderingAll] = useState(false);

  const {
    data: alerts = [],
    status,
    error,
    refetch,
  } = useApi(() => inventoryApi.getStockAlerts(), []);

  const categories = useMemo(
    () => Array.from(new Set(alerts.map((a) => a.category).filter(Boolean) as string[])),
    [alerts],
  );

  const filtered = useMemo(
    () =>
      alerts.filter((a) => {
        if (
          q &&
          !`${a.product_name} ${a.sku} ${a.brand ?? ""}`.toLowerCase().includes(q.toLowerCase())
        )
          return false;
        if (wh !== "all" && a.warehouse_city !== wh) return false;
        if (cat !== "all" && a.category !== cat) return false;
        return true;
      }),
    [alerts, q, wh, cat],
  );

  const needsAction = useMemo(() => filtered.filter((a) => !a.has_pending_order), [filtered]);
  const ordered = useMemo(() => filtered.filter((a) => a.has_pending_order), [filtered]);
  const totalCritical = alerts.filter(
    (a) => a.current_stock <= a.safety_stock && !a.has_pending_order,
  ).length;
  const totalOnWay = alerts.reduce((s, a) => s + a.incoming_qty, 0);
  const totalOrderedValue = ordered.reduce((s, a) => s + (a.pending_order_value || 0), 0);
  const selectedVendor = rankedVendors.find((v) => String(v.supplier_id) === selectedVendorId);
  const selectedUnitCost =
    selectedVendor?.landed_cost ??
    selectedVendor?.supplier_price ??
    selectedVendor?.avg_cost_index ??
    0;
  const selectedOrderQty = Math.max(0, Number(reorderQty) || 0);
  const selectedOrderTotal = selectedOrderQty * selectedUnitCost;

  // Load vendors for individual reorder
  useEffect(() => {
    if (reorderAlert) {
      setRankedVendors([]);
      setSelectedVendorId("");
      setReorderQty(String(Math.max(reorderAlert.reorder_point - reorderAlert.current_stock, 100)));
      procurementApi
        .rankVendors(reorderAlert.product_id, reorderAlert.warehouse_id)
        .then((vendors) => {
          setRankedVendors(vendors);
          if (vendors.length > 0) setSelectedVendorId(String(vendors[0].supplier_id));
        })
        .catch(() => toast.error("Failed to load vendors"));
    }
  }, [reorderAlert]);

  // Load vendors for Reorder All
  useEffect(() => {
    if (reorderAllOpen && allVendors.length === 0) {
      // Use first alert's product to get a ranked vendor list as default
      const firstAlert = needsAction[0];
      if (firstAlert) {
        procurementApi
          .rankVendors(firstAlert.product_id, firstAlert.warehouse_id)
          .then((vendors) => {
            setAllVendors(vendors);
            if (vendors.length > 0) setAllVendorId(String(vendors[0].supplier_id));
          })
          .catch(() => toast.error("Failed to load vendors"));
      }
    }
  }, [reorderAllOpen, allVendors.length, needsAction]);

  const handleReorder = async () => {
    if (!reorderAlert || !selectedVendorId) return;
    setIsReordering(true);
    try {
      await procurementApi.reorderProduct(
        reorderAlert.product_id,
        Number(selectedVendorId),
        Number(reorderQty),
        reorderAlert.warehouse_id,
      );
      toast.success(
        `✅ PO created for ${reorderAlert.product_name} at ${reorderAlert.warehouse_city ?? "WH-" + reorderAlert.warehouse_id} — ${reorderQty} units on the way!`,
      );
      setReorderAlert(null);
      refetch();
    } catch (e: unknown) {
      toast.error(`Failed to reorder: ${errorMessage(e)}`);
    } finally {
      setIsReordering(false);
    }
  };

  const handleReorderAll = async () => {
    if (!allVendorId) return;
    setIsReorderingAll(true);
    try {
      const res = await procurementApi.reorderAll(Number(allVendorId), Number(allQty));
      if (res.orders_created > 0) {
        toast.success(`✅ Created ${res.orders_created} purchase orders for all low-stock items.`);
      } else {
        toast.info("No items currently below reorder point.");
      }
      setReorderAllOpen(false);
      refetch();
    } catch (e: unknown) {
      toast.error(`Failed: ${errorMessage(e)}`);
    } finally {
      setIsReorderingAll(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Inventory management"
        subtitle="Stock alerts, reorders, and incoming units across all warehouses."
        actions={
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => setReorderAllOpen(true)}
            disabled={needsAction.length === 0}
          >
            <ShoppingCart className="w-4 h-4" />
            Reorder All ({needsAction.length})
          </Button>
        }
      />

      {/* KPI strip */}
      <div className="grid grid-cols-1 gap-3 mb-6 sm:grid-cols-3">
        <MiniKpi
          label="Critical (no PO)"
          value={totalCritical}
          description="Products at or below safety stock that do not yet have a pending purchase order."
          icon={AlertTriangle}
          accent="destructive"
        />
        <MiniKpi
          label="Need Reorder"
          value={needsAction.length}
          description="Filtered products below reorder point where the team still needs to place an order."
          icon={Boxes}
          accent="warning"
        />
        <MiniKpi
          label="Units On The Way"
          value={totalOnWay.toLocaleString()}
          description="Total incoming units from purchase orders that are still open or in transit."
          icon={TruckIcon}
          accent="info"
        />
      </div>

      {/* Filters */}
      <SectionCard className="mb-6">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[16rem]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search SKU, product, brand…"
              className="pl-9"
            />
          </div>
          <Select value={wh} onValueChange={setWh}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Warehouse" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All warehouses</SelectItem>
              {CITIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={cat} onValueChange={setCat}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon">
            <Filter className="w-4 h-4" />
          </Button>
        </div>
      </SectionCard>

      {status === "loading" && (
        <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading stock alerts…
        </div>
      )}
      {status === "error" && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center text-sm text-destructive">
          Failed to load: {error}
        </div>
      )}
      {status === "success" && (
        <Tabs defaultValue="alerts">
          <TabsList className="mb-4">
            <TabsTrigger value="alerts" className="gap-2">
              <AlertTriangle className="w-3.5 h-3.5" />
              Needs Reorder
              <Badge variant="destructive" className="ml-1 text-[10px]">
                {needsAction.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="ordered" className="gap-2">
              <PackageCheck className="w-3.5 h-3.5" />
              Ordered
              <Badge className="ml-1 text-[10px] bg-info/10 text-info border border-info/20">
                {ordered.length}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="alerts">
            <div className="rounded-2xl border border-border bg-card shadow-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-muted/60 backdrop-blur z-10">
                    {TABLE_HEAD}
                  </thead>
                  <tbody>
                    {needsAction.map((a, i) => (
                      <AlertRow
                        key={`${a.product_id}-${a.warehouse_id}`}
                        alert={a}
                        idx={i}
                        onReorder={setReorderAlert}
                      />
                    ))}
                  </tbody>
                </table>
                {needsAction.length === 0 && (
                  <div className="p-12 text-center text-muted-foreground">
                    <Boxes className="w-10 h-10 mx-auto opacity-30 mb-2" />
                    All low-stock items have pending orders.
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground">
                <div>{needsAction.length} items needing action</div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="ordered">
            <div className="rounded-2xl border border-border bg-card shadow-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-muted/60 backdrop-blur z-10">
                    {TABLE_HEAD}
                  </thead>
                  <tbody>
                    {ordered.map((a, i) => (
                      <OrderedRow key={`${a.product_id}-${a.warehouse_id}`} alert={a} idx={i} />
                    ))}
                  </tbody>
                </table>
                {ordered.length === 0 && (
                  <div className="p-12 text-center text-muted-foreground">
                    <PackageCheck className="w-10 h-10 mx-auto opacity-30 mb-2" />
                    No pending purchase orders yet.
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground">
                <div>
                  {ordered.length} items · {totalOnWay.toLocaleString()} total units incoming ·{" "}
                  {formatCurrency(totalOrderedValue)} ordered value
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      )}

      {/* Individual Reorder Modal */}
      <Dialog open={!!reorderAlert} onOpenChange={(val) => !val && setReorderAlert(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Reorder · {reorderAlert?.product_name}</DialogTitle>
            <DialogDescription>
              Current: <b>{reorderAlert?.current_stock}</b> units · Reorder point:{" "}
              <b>{reorderAlert?.reorder_point}</b>
              {reorderAlert?.incoming_qty
                ? ` · ${reorderAlert.incoming_qty} already on the way`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-1.5">
              <Label className="text-xs">Vendor recommendation</Label>
              {rankedVendors.length === 0 ? (
                <div className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading vendors…
                </div>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {rankedVendors.map((v) => (
                    <VendorOptionCard
                      key={v.supplier_id}
                      vendor={v}
                      selected={selectedVendorId === String(v.supplier_id)}
                      onSelect={() => setSelectedVendorId(String(v.supplier_id))}
                    />
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Quantity to order</Label>
              <Input
                type="number"
                value={reorderQty}
                onChange={(e) => setReorderQty(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Suggested:{" "}
                {reorderAlert
                  ? Math.max(reorderAlert.reorder_point - reorderAlert.current_stock, 100)
                  : 100}{" "}
                units
              </p>
              <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Estimated order value</span>
                  <span className="font-semibold tabular-nums">
                    {formatCurrency(selectedOrderTotal)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {selectedOrderQty.toLocaleString()} units x {formatCurrency(selectedUnitCost)}{" "}
                  selected vendor cost
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReorderAlert(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleReorder}
              disabled={!selectedVendorId || isReordering}
              className="gradient-primary text-primary-foreground border-0"
            >
              {isReordering && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Submit Order
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reorder All Modal */}
      <Dialog open={reorderAllOpen} onOpenChange={setReorderAllOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reorder All Low-Stock Items</DialogTitle>
            <DialogDescription>
              This will create purchase orders for all <b>{needsAction.length}</b> items that need
              restocking.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-1.5">
              <Label className="text-xs">Preferred Vendor</Label>
              {allVendors.length === 0 ? (
                <div className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading vendors…
                </div>
              ) : (
                <Select value={allVendorId} onValueChange={setAllVendorId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select vendor…" />
                  </SelectTrigger>
                  <SelectContent>
                    {allVendors.map((v) => (
                      <SelectItem key={v.supplier_id} value={String(v.supplier_id)}>
                        {v.supplier_name} - {vendorLabel(v)} - {formatScore(v.composite_score)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Quantity per product</Label>
              <Input type="number" value={allQty} onChange={(e) => setAllQty(e.target.value)} />
            </div>
            <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs text-warning">
              This will create {needsAction.length} purchase orders at {allQty} units each.
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReorderAllOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleReorderAll}
              disabled={!allVendorId || isReorderingAll}
              className="gradient-primary text-primary-foreground border-0"
            >
              {isReorderingAll && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Create {needsAction.length} Orders
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

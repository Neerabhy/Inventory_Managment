import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useState } from "react";
import { AlertTriangle, Loader2, MapPin, PackageCheck, Send, ShoppingCart } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/useApi";
import { logisticsApi, type InboundOrder, type Shipment } from "@/lib/api/logistics";

export const Route = createFileRoute("/app/logistics")({
  head: () => ({ meta: [{ title: "Logistics Tracking - AI Inventory Copilot" }] }),
  component: Logistics,
});

type LogisticsTab = "placed" | "inbound" | "outbound";

type MovementItem = {
  id: string;
  code: string;
  type: LogisticsTab;
  title: string;
  subtitle: string;
  status: string;
  origin: string;
  destination: string;
  amount?: number | null;
  quantity?: number | null;
  partner?: string | null;
  expectedLabel?: string | null;
  expectedTitle?: string | null;
  delayDays?: number | null;
  shipmentCode?: string | null;
};

const typeMeta = {
  placed: { label: "Order placed", icon: ShoppingCart, progress: "18%" },
  inbound: { label: "Inbound", icon: PackageCheck, progress: "62%" },
  outbound: { label: "Outbound", icon: Send, progress: "62%" },
};

function statusClass(status: string, delayDays?: number | null) {
  const s = status.toUpperCase();
  if (s === "DELIVERED") return "bg-success/10 text-success";
  if (s === "DELAYED" || (delayDays ?? 0) > 0) return "bg-destructive/10 text-destructive";
  if (s.includes("TRANSIT") || s === "SHIPPED") return "bg-info/10 text-info";
  return "bg-muted text-muted-foreground";
}

function MovementCard({ item, idx }: { item: MovementItem; idx: number }) {
  const meta = typeMeta[item.type];
  const Icon = meta.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.03 }}
      className="rounded-2xl border border-border bg-card p-4 transition hover:shadow-elevated"
    >
      <div className="mb-3 flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs">{item.code}</span>
            <Badge variant="outline" className="text-[10px] uppercase">
              {meta.label}
            </Badge>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider ${statusClass(
                item.status,
                item.delayDays,
              )}`}
            >
              {item.status.replace(/_/g, " ")}
            </span>
          </div>
          <div className="mt-1 truncate text-sm font-medium">{item.title}</div>
          <div className="text-xs text-muted-foreground">{item.subtitle}</div>
        </div>
        {isDelayed(item) && (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle className="h-3 w-3" />
            {formatDelay(item.delayDays)}
          </Badge>
        )}
      </div>

      <div className="mb-3 flex items-center gap-2">
        <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-sm font-medium">{item.origin}</span>
        <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-muted">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: item.status.toUpperCase() === "DELIVERED" ? "100%" : meta.progress }}
            transition={{ duration: 1, delay: idx * 0.05 }}
            className="absolute inset-y-0 left-0 rounded-full gradient-primary"
          />
        </div>
        <span className="text-sm font-medium">{item.destination}</span>
        <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        <Fact
          label="Expected"
          value={item.expectedLabel ?? "Not set"}
          title={item.expectedTitle ?? undefined}
        />
        <Fact label="Quantity" value={(item.quantity ?? 1).toLocaleString()} />
        <Fact label="Value" value={formatCurrency(item.amount)} />
        <Fact label="Partner" value={item.partner ?? "Not assigned"} />
        <Fact label="Shipment" value={item.shipmentCode ?? "Not assigned"} />
      </div>
    </motion.div>
  );
}

function Logistics() {
  const [activeTab, setActiveTab] = useState<LogisticsTab>("placed");
  const {
    data: shipments = [],
    status,
    error,
  } = useApi(() => logisticsApi.listShipments({ limit: 500 }), []);
  const { data: allPurchaseOrders = [], status: orderStatus } = useApi(
    () => logisticsApi.listInboundOrders({ include_closed: true, limit: 500 }),
    [],
  );
  const { data: summary } = useApi(() => logisticsApi.summary(), []);

  const orderPlaced = allPurchaseOrders.filter((order) => !order.has_shipment);
  const inbound = allPurchaseOrders.filter((order) => order.has_shipment);
  const outbound = shipments.filter((s) =>
    ["OUTBOUND", "FORWARD"].includes(s.direction?.toUpperCase() ?? ""),
  );

  const placedItems = orderPlaced.map(orderToMovement("placed"));
  const inboundItems = inbound.map(orderToMovement("inbound"));
  const outboundItems = outbound.map(shipmentToMovement);
  const activeItems =
    activeTab === "placed" ? placedItems : activeTab === "inbound" ? inboundItems : outboundItems;

  const kpis = [
    { l: "Total Orders", v: summary?.total_orders ?? "-", c: "text-foreground" },
    { l: "Orders Placed", v: summary?.orders_placed ?? orderPlaced.length, c: "text-primary" },
    { l: "Inbound Orders", v: summary?.inbound_orders ?? inbound.length, c: "text-info" },
    { l: "Outbound Orders", v: summary?.outbound_orders ?? outbound.length, c: "text-success" },
    { l: "Delay Rate", v: summary ? `${summary.delay_rate_pct}%` : "-", c: "text-destructive" },
  ];

  const routeData = buildRouteData(activeItems);

  return (
    <>
      <PageHeader
        title="Logistics tracking"
        subtitle="Orders placed, inbound procurement movement, and outbound shipment movement."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        {kpis.map((k) => (
          <div key={k.l} className="rounded-2xl border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground">{k.l}</div>
            <div className={`mt-1 text-xl font-semibold ${k.c}`}>{k.v}</div>
          </div>
        ))}
      </div>

      {(status === "loading" || orderStatus === "loading") && (
        <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading logistics...
        </div>
      )}
      {status === "error" && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center text-sm text-destructive">
          Failed to load shipments: {error}
        </div>
      )}
      {status === "success" && orderStatus === "success" && (
        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as LogisticsTab)}
          className="mb-6"
        >
          <TabsList>
            <TabsTrigger value="placed">Orders placed ({placedItems.length})</TabsTrigger>
            <TabsTrigger value="inbound">Inbound ({inboundItems.length})</TabsTrigger>
            <TabsTrigger value="outbound">Outbound ({outboundItems.length})</TabsTrigger>
          </TabsList>
          <MovementTab
            items={placedItems}
            empty="No placed purchase orders waiting for shipment."
          />
          <MovementTab
            value="inbound"
            items={inboundItems}
            empty="No inbound shipment-linked orders found."
          />
          <MovementTab value="outbound" items={outboundItems} empty="No outbound orders found." />
        </Tabs>
      )}

      {routeData.length > 0 && (
        <SectionCard
          title="Active routes"
          subtitle={`Route volume for ${typeMeta[activeTab].label.toLowerCase()} section`}
        >
          <div style={{ height: Math.max(260, routeData.length * 34) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={routeData} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                  horizontal={false}
                />
                <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="route"
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  width={160}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Bar dataKey="count" fill="var(--color-chart-2)" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      )}
    </>
  );
}

function MovementTab({
  value = "placed",
  items,
  empty,
}: {
  value?: string;
  items: MovementItem[];
  empty: string;
}) {
  return (
    <TabsContent value={value} className="mt-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items.map((item, i) => (
          <MovementCard key={item.id} item={item} idx={i} />
        ))}
      </div>
      {items.length === 0 && (
        <div className="py-12 text-center text-sm text-muted-foreground">{empty}</div>
      )}
    </TabsContent>
  );
}

function orderToMovement(type: "placed" | "inbound") {
  return (order: InboundOrder): MovementItem => ({
    id: `po-${order.id}`,
    code: order.po_code ?? `PO-${String(order.id).padStart(5, "0")}`,
    type,
    title: order.product_name,
    subtitle: `${order.sku ?? "No SKU"} · ${order.quantity.toLocaleString()} units from ${order.supplier_name}`,
    status: order.shipment_status ?? order.status ?? "Draft",
    origin: order.origin_city ?? "Supplier",
    destination: order.destination_city ?? order.warehouse_city ?? "Warehouse",
    amount: order.total_amount,
    quantity: order.quantity,
    partner: order.delivery_partner,
    expectedLabel: order.expected_delivery ? formatDate(order.expected_delivery) : null,
    expectedTitle: order.expected_delivery ? "Expected delivery date" : null,
    delayDays: order.delay_days,
    shipmentCode: order.shipment_code,
  });
}

function shipmentToMovement(s: Shipment): MovementItem {
  return {
    id: `shipment-${s.id}`,
    code: s.shipment_code ?? `SHP-${String(s.id).padStart(5, "0")}`,
    type: "outbound",
    title: `Outbound shipment ${s.shipment_code ?? s.id}`,
    subtitle: s.distance_km
      ? `${Number(s.distance_km).toFixed(0)} km · ${s.carrier ?? "Partner not assigned"} · Shipping ${formatCurrency(s.estimated_cost)}`
      : `${s.carrier ?? "Partner not assigned"} outbound movement`,
    status: s.status ?? "Pending",
    origin: s.origin_city ?? "Warehouse",
    destination: s.destination_city ?? "Customer",
    amount: s.actual_cost,
    quantity: 1,
    partner: s.carrier,
    expectedLabel: s.expected_delivery_days ? `${s.expected_delivery_days}d` : null,
    expectedTitle: s.expected_delivery_days
      ? `Expected delivery duration: ${s.expected_delivery_days} days`
      : null,
    delayDays: s.delay_days,
    shipmentCode: s.shipment_code,
  };
}

function buildRouteData(items: MovementItem[]) {
  const routeMap: Record<string, number> = {};
  items.forEach((item) => {
    if (item.origin && item.destination) {
      const key = `${item.origin} -> ${item.destination}`;
      routeMap[key] = (routeMap[key] ?? 0) + 1;
    }
  });
  return Object.entries(routeMap)
    .sort(([, a], [, b]) => b - a)
    .reduce<{ route: string; count: number }[]>((acc, [route, count], index) => {
      if (index < 5) {
        acc.push({ route, count });
      } else {
        const others = acc.find((item) => item.route === "Others");
        if (others) others.count += count;
        else acc.push({ route: "Others", count });
      }
      return acc;
    }, []);
}

function isDelayed(item: MovementItem) {
  return item.status.toUpperCase() === "DELAYED" || (item.delayDays ?? 0) > 0;
}

function formatDelay(delayDays?: number | null) {
  if ((delayDays ?? 0) <= 0) return "Delayed";
  return `Delayed by ${delayDays}d`;
}

function Fact({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="rounded-md bg-muted/30 px-2 py-1.5" title={title}>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="truncate font-medium tabular-nums">{value}</div>
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

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

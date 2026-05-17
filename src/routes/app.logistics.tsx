import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { shipments } from "@/lib/mock/data";
import { Badge } from "@/components/ui/badge";
import { Truck, Plane, Train, MapPin, Clock, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const Route = createFileRoute("/app/logistics")({
  head: () => ({ meta: [{ title: "Logistics Tracking — AI Inventory Copilot" }] }),
  component: Logistics,
});

const modeIcon: Record<string, any> = { road: Truck, air: Plane, rail: Train };

function ShipmentRow({ s, idx }: { s: typeof shipments[number]; idx: number }) {
  const Icon = modeIcon[s.transportation_mode] ?? Truck;
  const statusColor = s.shipment_status === "delivered" ? "bg-success/10 text-success"
    : s.shipment_status === "delayed" ? "bg-destructive/10 text-destructive"
    : s.shipment_status === "in_transit" ? "bg-info/10 text-info"
    : "bg-muted text-muted-foreground";

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.03 }}
      className="rounded-2xl border border-border bg-card p-4 hover:shadow-elevated transition"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary grid place-items-center"><Icon className="w-5 h-5" /></div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{s.shipment_id}</span>
            <Badge variant="outline" className="text-[10px] uppercase">{s.shipment_type}</Badge>
            <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${statusColor}`}>{s.shipment_status.replace("_", " ")}</span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">{s.logistics_provider} · {s.distance_km}km</div>
        </div>
        {s.delayed_flag && (
          <Badge variant="destructive" className="gap-1"><AlertTriangle className="w-3 h-3" />+{s.actual_delivery_days - s.expected_delivery_days}d</Badge>
        )}
      </div>
      <div className="flex items-center gap-2 mb-2">
        <MapPin className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-sm font-medium">{s.source_city}</span>
        <div className="flex-1 relative h-1 bg-muted rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${s.eta_progress}%` }}
            transition={{ duration: 1, delay: idx * 0.05 }}
            className="absolute inset-y-0 left-0 gradient-primary rounded-full"
          />
          <span className="absolute -top-1.5 w-2 h-2 rounded-full gradient-primary shadow-glow" style={{ left: `calc(${s.eta_progress}% - 4px)` }} />
        </div>
        <span className="text-sm font-medium">{s.destination_city}</span>
        <MapPin className="w-3.5 h-3.5 text-muted-foreground" />
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground mt-2">
        <span className="inline-flex items-center gap-1"><Clock className="w-3 h-3" />Expected {s.expected_delivery_days}d · Actual {s.actual_delivery_days}d</span>
        <span>₹{s.shipping_cost.toLocaleString()}</span>
      </div>
    </motion.div>
  );
}

function Logistics() {
  const inbound = shipments.filter((s) => s.shipment_type === "inbound");
  const outbound = shipments.filter((s) => s.shipment_type === "outbound");

  const kpis = [
    { l: "Avg Delivery Time", v: "4.2d", c: "text-foreground" },
    { l: "Shipment Success Rate", v: "94.3%", c: "text-success" },
    { l: "Delayed Orders", v: "31", c: "text-destructive" },
    { l: "Logistics Cost", v: "₹2.4M", c: "text-foreground" },
    { l: "Damage Rate", v: "0.8%", c: "text-warning" },
  ];

  const routeData = [
    { route: "Mumbai → Delhi", count: 84 },
    { route: "Bangalore → Kolkata", count: 56 },
    { route: "Delhi → Jaipur", count: 47 },
    { route: "Mumbai → Bangalore", count: 41 },
    { route: "Kolkata → Mumbai", count: 28 },
  ];

  return (
    <>
      <PageHeader title="Logistics tracking" subtitle="Inbound and outbound shipment intelligence with delay prediction." />
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {kpis.map((k) => (
          <div key={k.l} className="rounded-2xl border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground">{k.l}</div>
            <div className={`text-xl font-semibold mt-1 ${k.c}`}>{k.v}</div>
          </div>
        ))}
      </div>

      <Tabs defaultValue="all" className="mb-6">
        <TabsList>
          <TabsTrigger value="all">All ({shipments.length})</TabsTrigger>
          <TabsTrigger value="inbound">Inbound ({inbound.length})</TabsTrigger>
          <TabsTrigger value="outbound">Outbound ({outbound.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="all" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {shipments.map((s, i) => <ShipmentRow key={s.shipment_id} s={s} idx={i} />)}
          </div>
        </TabsContent>
        <TabsContent value="inbound" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {inbound.map((s, i) => <ShipmentRow key={s.shipment_id} s={s} idx={i} />)}
          </div>
        </TabsContent>
        <TabsContent value="outbound" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {outbound.map((s, i) => <ShipmentRow key={s.shipment_id} s={s} idx={i} />)}
          </div>
        </TabsContent>
      </Tabs>

      <SectionCard title="Top routes" subtitle="Shipment volume across active corridors">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={routeData} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} />
              <YAxis type="category" dataKey="route" stroke="var(--color-muted-foreground)" fontSize={11} width={150} />
              <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
              <Bar dataKey="count" fill="var(--color-chart-2)" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </SectionCard>
    </>
  );
}

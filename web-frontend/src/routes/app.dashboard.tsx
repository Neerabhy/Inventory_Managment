import { createFileRoute, Link } from "@tanstack/react-router";
import {
  DollarSign,
  ShoppingBag,
  RotateCcw,
  Boxes,
  Truck,
  ShoppingCart,
  AlertTriangle,
  Sparkles,
  ChevronRight,
} from "lucide-react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/useApi";
import { inventoryApi } from "@/lib/api/inventory";
import { analyticsApi } from "@/lib/api/analytics";
import { returnsApi } from "@/lib/api/returns";
import { logisticsApi } from "@/lib/api/logistics";

export const Route = createFileRoute("/app/dashboard")({
  head: () => ({ meta: [{ title: "Operations Dashboard — AI Inventory Copilot" }] }),
  component: Dashboard,
});

const sparkFrom = (values: number[]) => {
  if (values.length === 0) return undefined;
  return values.map((v) => ({ v: Math.max(0, v) }));
};

const formatPct = (value: number) => `${value.toFixed(1)}%`;

function Dashboard() {
  // --- KPI definitions (names, formulas, thresholds) ---
  const { data: kpis = [] } = useApi(() => inventoryApi.listKpis(), []);
  const kpiMap = Object.fromEntries(kpis.map((k) => [k.kpi_code, k]));

  // --- Chart data ---
  const { data: summary } = useApi(() => analyticsApi.getDashboardSummary(), []);
  const { data: charts } = useApi(() => analyticsApi.getDashboardCharts(), []);
  const { data: forecastSeries = [] } = useApi(() => analyticsApi.getForecastSeries(), []);
  const { data: landingStats } = useApi(() => analyticsApi.getLandingStats(), []);

  // --- Operational data for KPI values ---
  const { data: returnsSummary } = useApi(() => returnsApi.summary(), []);
  const { data: delayData } = useApi(() => logisticsApi.delayAnalysis(), []);
  const { data: lowStockItems = [] } = useApi(
    () => inventoryApi.listStock({ below_reorder: true }),
    [],
  );

  const revenueTrend = charts?.revenueTrend ?? [];
  const categoryPerf = charts?.categoryPerf ?? [];
  const returnReasons = charts?.returnReasons ?? [];
  const shipmentDelayBuckets = charts?.shipmentDelayBuckets ?? [];

  const revenueSpark = sparkFrom(revenueTrend.map((d) => d.revenue));
  const salesOrdersSpark = sparkFrom(revenueTrend.map((d) => d.orders));
  const unitsSpark = sparkFrom(revenueTrend.map((d) => d.units));
  const shipmentSpark = sparkFrom(shipmentDelayBuckets.map((d) => d.value));

  // --- Dynamic alerts from real data ---
  const dynamicAlerts: {
    sev: "destructive" | "warning";
    title: string;
    desc: string;
    time: string;
  }[] = [];

  lowStockItems.slice(0, 2).forEach((s) => {
    dynamicAlerts.push({
      sev: "destructive",
      title: `Low stock — ${s.warehouse_city ?? "Warehouse"}`,
      desc: `${s.quantity_on_hand} units remaining · safety stock ${s.safety_stock ?? 40}`,
      time: "Live",
    });
  });

  if (delayData && delayData.delayed_count > 0) {
    dynamicAlerts.push({
      sev: "destructive",
      title: `${delayData.delayed_count} shipments delayed`,
      desc: `Avg ${delayData.avg_delay_days}d late · ${delayData.delay_rate_pct}% of total`,
      time: "Live",
    });
  }

  if (returnsSummary && returnsSummary.high_risk > 0) {
    dynamicAlerts.push({
      sev: "warning",
      title: "High fraud-risk returns pending",
      desc: `${returnsSummary.high_risk} returns above fraud threshold`,
      time: "Live",
    });
  }

  if (returnsSummary && returnsSummary.anomaly_flagged > 0) {
    dynamicAlerts.push({
      sev: "warning",
      title: "ML anomalies flagged in returns",
      desc: `${returnsSummary.anomaly_flagged} returns flagged · ${returnsSummary.pending} pending review`,
      time: "Recent",
    });
  }

  // Live alerts only; empty state is rendered when database signals are healthy.
  const ALERTS = dynamicAlerts;
  const aiInsights = landingStats?.insights
    ? landingStats.insights.map((str) => {
        const parts = str.split(/(?:—|:|-)/);
        return {
          t: parts[0]?.trim() || str,
          c: parts.slice(1).join(" - ").trim() || "Action required.",
        };
      })
    : [
        {
          t: `Sales revenue at Rs ${Math.round(summary?.total_revenue ?? 0).toLocaleString()}`,
          c: `${summary?.sales_orders ?? 0} sales orders and ${summary?.units_sold ?? 0} units sold are recorded in the sales table.`,
        },
        {
          t: `Logistics delay rate ${formatPct(summary?.delay_rate_pct ?? 0)}`,
          c: `${summary?.delayed_shipments ?? 0} delayed out of ${summary?.total_shipments ?? 0} shipment records.`,
        },
        {
          t: `Inventory health ${formatPct(summary?.inventory_health_pct ?? 0)}`,
          c: `${lowStockItems.length} stock rows are currently below reorder or safety thresholds.`,
        },
        {
          t: `Open purchase orders: ${summary?.open_purchase_orders ?? 0}`,
          c: `PO spend to date is Rs ${Math.round(summary?.procurement_spend ?? 0).toLocaleString()} from purchase order quantities and unit costs.`,
        },
      ];

  return (
    <>
      <PageHeader
        title="Operations control center"
        subtitle="Real-time intelligence across inventory, procurement, logistics and returns."
        actions={
          <>
            <Badge variant="secondary" className="gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              Live
            </Badge>
            <Button variant="outline" size="sm">
              Last 30 days
            </Button>
            <Button size="sm" asChild className="gradient-primary text-primary-foreground border-0">
              <Link to="/app/copilot">
                <Sparkles className="w-3.5 h-3.5 mr-1" /> Ask AI
              </Link>
            </Button>
          </>
        }
      />

      {/* KPI grid — all values computed from live API data */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label={kpiMap.TOTAL_REVENUE?.kpi_name || "Sales Revenue"}
          value={summary?.total_revenue ?? 0}
          prefix="Rs "
          delta={summary?.deltas.total_revenue ?? 0}
          icon={DollarSign}
          sparkline={revenueSpark}
          tooltip={kpiMap.TOTAL_REVENUE?.description || "All-time customer sales revenue"}
          tooltipMeaning="Shows the money earned from customer sales only."
          tooltipCalc="Add the final amount from every customer sale."
          accent="primary"
        />
        <KpiCard
          label="Sales Orders"
          value={summary?.sales_orders ?? 0}
          delta={summary?.deltas.sales_orders ?? 0}
          icon={ShoppingBag}
          sparkline={salesOrdersSpark}
          tooltip="Customer sales order count"
          tooltipMeaning="Demand volume. This does not include purchase orders or logistics shipments."
          tooltipCalc="Count every customer sales order recorded in the database."
          accent="info"
        />
        <KpiCard
          label="Units Sold"
          value={summary?.units_sold ?? 0}
          delta={summary?.deltas.units_sold ?? 0}
          icon={Boxes}
          sparkline={unitsSpark}
          tooltip="Total product units sold"
          tooltipMeaning="Useful for inventory planning because one order can contain multiple units."
          tooltipCalc="Add the quantity sold from every sales order."
          accent="success"
        />
        <KpiCard
          label="Return Rate"
          value={summary?.return_rate_pct ?? 0}
          suffix="%"
          decimals={1}
          delta={summary?.deltas.return_rate_pct ?? 0}
          trendText="All-time rate"
          icon={RotateCcw}
          tooltip={kpiMap.RETURN_RATE?.description || "Returns as a percentage of sales orders"}
          tooltipMeaning="Lower is better. It reflects quality, fit, fulfillment, and customer experience."
          tooltipCalc="Divide the number of returns by the number of sales orders, then convert it to a percentage."
          accent="warning"
        />
        <KpiCard
          label="Inventory Health"
          value={summary?.inventory_health_pct ?? 0}
          suffix="%"
          decimals={1}
          delta={0}
          trendText="Current stock position"
          icon={Boxes}
          tooltip="Share of inventory rows at or above safety stock"
          tooltipMeaning="Quick signal for stockout risk across warehouses."
          tooltipCalc="Check how many warehouse stock records are at or above safety stock, then show that share as a percentage."
          accent="success"
        />
        <KpiCard
          label="Logistics Shipments"
          value={summary?.total_shipments ?? 0}
          delta={summary?.deltas.total_shipments ?? 0}
          trendText="All-time shipment count"
          icon={Truck}
          sparkline={shipmentSpark}
          tooltip="Total shipment records"
          tooltipMeaning="Logistics throughput till now. This is intentionally separate from sales and purchase orders."
          tooltipCalc="Count every inbound and outbound shipment record."
          accent="info"
        />
        <KpiCard
          label="PO Spend"
          value={summary?.procurement_spend ?? 0}
          prefix="Rs "
          delta={summary?.deltas.procurement_spend ?? 0}
          trendText="All-time PO value"
          icon={ShoppingCart}
          tooltip="Purchase order spend to date"
          tooltipMeaning="Shows committed procurement value from purchase orders, not an invented cost."
          tooltipCalc="For every purchase order, multiply ordered quantity by unit cost, then add all order values."
          accent="warning"
        />
        <KpiCard
          label="Open Purchase Orders"
          value={summary?.open_purchase_orders ?? 0}
          delta={0}
          trendText="Currently open"
          icon={ShoppingCart}
          tooltip="Purchase orders not yet closed"
          tooltipMeaning="Shows supplier-side work still in progress and helps explain inbound pipeline pressure."
          tooltipCalc="Count purchase orders that are still waiting, approved, ordered, shipped, or in transit."
          accent="primary"
        />
      </div>

      {/* Alerts + AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <SectionCard
          title="Operational alerts"
          subtitle="Issues that need attention now"
          actions={
            <Badge variant="destructive" className="text-[10px]">
              {ALERTS.length} active
            </Badge>
          }
          className="lg:col-span-1"
        >
          <ul className="space-y-2.5">
            {ALERTS.length === 0 && (
              <li className="rounded-xl border border-border p-3 text-sm text-muted-foreground">
                No live alerts from current database signals.
              </li>
            )}
            {ALERTS.map((a, i) => (
              <li
                key={i}
                className="flex gap-3 rounded-xl border border-border p-3 hover:bg-muted/40 transition"
              >
                <div
                  className={`mt-0.5 w-8 h-8 rounded-lg grid place-items-center flex-shrink-0 ${
                    a.sev === "destructive"
                      ? "bg-destructive/10 text-destructive"
                      : "bg-warning/10 text-warning"
                  }`}
                >
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium leading-tight">{a.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{a.desc}</div>
                  <div className="text-[10px] text-muted-foreground mt-1.5">{a.time}</div>
                </div>
              </li>
            ))}
          </ul>
        </SectionCard>

        <SectionCard
          title="AI Insights"
          subtitle="Generated by Copilot · 2m ago"
          actions={<Sparkles className="w-4 h-4 text-primary" />}
          className="lg:col-span-2"
        >
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {aiInsights.map((insight, idx) => (
              <li
                key={idx}
                className="rounded-xl border border-border p-4 bg-gradient-to-br from-primary/5 to-transparent group hover:border-primary/30 transition"
              >
                <div className="flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium leading-snug">{insight.t}</div>
                    <div className="text-xs text-muted-foreground mt-1.5">{insight.c}</div>
                    <button className="mt-2 text-xs text-primary inline-flex items-center gap-1 opacity-80 group-hover:opacity-100">
                      Investigate <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SectionCard title="Revenue trend" subtitle="Last 30 days" className="lg:col-span-2">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={revenueTrend}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
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
                <YAxis
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                />
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
                  fill="url(#revGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Shipment delays" subtitle="Buckets · last 30d">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={shipmentDelayBuckets}
                  dataKey="value"
                  nameKey="bucket"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                >
                  {shipmentDelayBuckets.map((_, i) => (
                    <Cell key={i} fill={`var(--color-chart-${i + 1})`} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard
          title="Category performance"
          subtitle="Revenue by category"
          className="lg:col-span-2"
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryPerf}>
                <CartesianGrid
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                  vertical={false}
                />
                <XAxis dataKey="category" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Bar dataKey="revenue" fill="var(--color-chart-1)" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Forecast vs actual" subtitle="Units · weekly">
          <div className="h-72">
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
                <Line
                  type="monotone"
                  dataKey="actual"
                  stroke="var(--color-chart-1)"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
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

        <SectionCard
          title="Return reasons"
          subtitle={`Top drivers · ${returnReasons.length} categories`}
          className="lg:col-span-3"
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={returnReasons} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                  horizontal={false}
                />
                <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="reason"
                  stroke="var(--color-muted-foreground)"
                  fontSize={11}
                  width={150}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Bar dataKey="count" fill="var(--color-chart-5)" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>
    </>
  );
}

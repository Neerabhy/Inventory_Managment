import { createFileRoute, Link } from "@tanstack/react-router";
import {
  DollarSign, ShoppingBag, RotateCcw, Boxes, Truck, ShoppingCart, ShieldAlert, TrendingUp,
  AlertTriangle, Sparkles, ChevronRight,
} from "lucide-react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { revenueTrend, categoryPerf, returnReasons, shipmentDelayBuckets, forecastSeries } from "@/lib/mock/data";

export const Route = createFileRoute("/app/dashboard")({
  head: () => ({ meta: [{ title: "Operations Dashboard — AI Inventory Copilot" }] }),
  component: Dashboard,
});

const spark = (n: number) =>
  Array.from({ length: 14 }, (_, i) => ({ v: n + Math.sin(i / 2) * (n * 0.15) + (Math.random() - 0.5) * n * 0.08 }));

const ALERTS = [
  { sev: "destructive", title: "Low stock — Sony WH-1000XM5", desc: "Mumbai WH · 14 units, below safety 40", time: "8m ago" },
  { sev: "warning", title: "Supplier SLA violation — S-03", desc: "On-time delivery dropped to 78% this week", time: "1h ago" },
  { sev: "destructive", title: "Inbound shipment delayed", desc: "SHP-00184 from Delhi → Bangalore (+3 days)", time: "2h ago" },
  { sev: "warning", title: "High fraud-risk return", desc: "R-00021 · score 0.87 · awaiting manual review", time: "3h ago" },
] as const;

const INSIGHTS = [
  { t: "Monitor returns up 18% — root cause: logistics damage", c: "Inspect inbound packaging changes from Q1 vendor switch." },
  { t: "Supplier S-03 defect rates impacting laptop returns", c: "Re-route 30% of next PO to Quantum Components." },
  { t: "Headphones demand peaks W3 next month (+24%)", c: "Pre-position 1,200 units across Mumbai & Bangalore." },
  { t: "Procurement saving available: ₹42k/month on cables", c: "Switch SKU CBL-* to Apex Hardware (cost index 0.86)." },
];

function Dashboard() {
  return (
    <>
      <PageHeader
        title="Operations control center"
        subtitle="Real-time intelligence across inventory, procurement, logistics and returns."
        actions={
          <>
            <Badge variant="secondary" className="gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />Live</Badge>
            <Button variant="outline" size="sm">Last 30 days</Button>
            <Button size="sm" asChild className="gradient-primary text-primary-foreground border-0">
              <Link to="/app/copilot"><Sparkles className="w-3.5 h-3.5 mr-1" /> Ask AI</Link>
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Revenue" value={4820000} prefix="₹" delta={12.4} icon={DollarSign} sparkline={spark(4820000)}
          tooltip="Total revenue (last 30d)" tooltipMeaning="Top-line health of the business across all channels."
          tooltipCalc="Σ(final_amount) for sales in window, net of refunds." accent="primary" />
        <KpiCard label="Orders" value={12408} delta={8.1} icon={ShoppingBag} sparkline={spark(12408)}
          tooltip="Total orders fulfilled" tooltipMeaning="Volume signal for fulfillment capacity planning."
          tooltipCalc="COUNT(sales) where order_status IN (shipped, delivered)." accent="info" />
        <KpiCard label="Return Rate" value={3.2} suffix="%" decimals={1} delta={-0.4} icon={RotateCcw} sparkline={spark(3.2)}
          tooltip="Returns / Orders %" tooltipMeaning="Lower is better. Tracks product-market fit and quality."
          tooltipCalc="returns / sales × 100 in the same window." accent="success" />
        <KpiCard label="Inventory Health" value={87.3} suffix="%" decimals={1} delta={2.1} icon={Boxes} sparkline={spark(87)}
          tooltip="Composite stock health score" tooltipMeaning="Aggregates safety stock, turnover and stockouts."
          tooltipCalc="weighted score of SKUs above reorder point." accent="success" />
        <KpiCard label="Delayed Shipments" value={31} delta={6.0} icon={Truck} sparkline={spark(31)}
          tooltip="Shipments past expected ETA" tooltipMeaning="Direct customer-experience risk."
          tooltipCalc="COUNT(shipments) where actual > expected." accent="destructive" />
        <KpiCard label="Procurement Cost" value={1820000} prefix="₹" delta={-3.2} icon={ShoppingCart} sparkline={spark(1820000)}
          tooltip="Total PO value (30d)" tooltipMeaning="Cost of goods sourced. Track against forecast."
          tooltipCalc="Σ(qty × unit_cost) for placed POs." accent="warning" />
        <KpiCard label="Fraud-Risk Returns" value={14} delta={2.0} icon={ShieldAlert} sparkline={spark(14)}
          tooltip="Returns above fraud threshold" tooltipMeaning="Direct margin protection signal."
          tooltipCalc="COUNT(returns) where fraud_risk_score > 0.7." accent="destructive" />
        <KpiCard label="Forecasted Demand" value={18450} delta={9.2} icon={TrendingUp} sparkline={spark(18450)}
          tooltip="Next 30d demand forecast (units)" tooltipMeaning="Driver for procurement and warehouse planning."
          tooltipCalc="Σ(P50 forecast) across active SKUs." accent="primary" />
      </div>

      {/* Alerts + AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <SectionCard
          title="Operational alerts"
          subtitle="Issues that need attention now"
          actions={<Badge variant="destructive" className="text-[10px]">4 active</Badge>}
          className="lg:col-span-1"
        >
          <ul className="space-y-2.5">
            {ALERTS.map((a, i) => (
              <li key={i} className="flex gap-3 rounded-xl border border-border p-3 hover:bg-muted/40 transition">
                <div className={`mt-0.5 w-8 h-8 rounded-lg grid place-items-center flex-shrink-0 ${
                  a.sev === "destructive" ? "bg-destructive/10 text-destructive" : "bg-warning/10 text-warning"
                }`}>
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
            {INSIGHTS.map((i, idx) => (
              <li key={idx} className="rounded-xl border border-border p-4 bg-gradient-to-br from-primary/5 to-transparent group hover:border-primary/30 transition">
                <div className="flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium leading-snug">{i.t}</div>
                    <div className="text-xs text-muted-foreground mt-1.5">{i.c}</div>
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
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Area type="monotone" dataKey="revenue" stroke="var(--color-chart-1)" strokeWidth={2} fill="url(#revGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Shipment delays" subtitle="Buckets · last 30d">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={shipmentDelayBuckets} dataKey="value" nameKey="bucket" innerRadius={55} outerRadius={90} paddingAngle={3}>
                  {shipmentDelayBuckets.map((_, i) => (
                    <Cell key={i} fill={`var(--color-chart-${i + 1})`} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Category performance" subtitle="Revenue by category" className="lg:col-span-2">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryPerf}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="category" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Bar dataKey="revenue" fill="var(--color-chart-1)" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Forecast vs actual" subtitle="Units · weekly">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastSeries}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Line type="monotone" dataKey="actual" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="forecast" stroke="var(--color-chart-3)" strokeWidth={2} strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Return reasons" subtitle="Top drivers" className="lg:col-span-3">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={returnReasons} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis type="category" dataKey="reason" stroke="var(--color-muted-foreground)" fontSize={11} width={150} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Bar dataKey="count" fill="var(--color-chart-5)" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>
    </>
  );
}

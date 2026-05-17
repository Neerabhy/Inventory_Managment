import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { products, suppliers, revenueTrend, forecastSeries } from "@/lib/mock/data";
import { ArrowLeft, Star, Sparkles, Award, Zap, IndianRupee } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { motion } from "framer-motion";

export const Route = createFileRoute("/app/products/$sku")({
  head: ({ params }) => ({ meta: [{ title: `${params.sku} — Product detail` }] }),
  component: Detail,
  loader: ({ params }) => {
    const p = products.find((x) => x.sku === params.sku);
    if (!p) throw notFound();
    return { product: p };
  },
  notFoundComponent: () => <div className="p-8">Product not found.</div>,
});

function Detail() {
  const { product: p } = Route.useLoaderData();
  // Pick 3 deterministic suppliers
  const linked = suppliers.slice(0, 3).map((s, i) => ({
    ...s,
    landed_cost: Math.round(p.manufacturing_cost * (0.95 + i * 0.07)),
    ai_score: +(0.95 - i * 0.08).toFixed(2),
    badge: i === 0 ? "BEST CHOICE" : i === 1 ? "LOWEST COST" : "FASTEST DELIVERY",
    badgeColor: i === 0 ? "bg-primary text-primary-foreground" : i === 1 ? "bg-success text-success-foreground" : "bg-info text-info-foreground",
    badgeIcon: i === 0 ? Award : i === 1 ? IndianRupee : Zap,
  }));

  return (
    <>
      <Button variant="ghost" size="sm" asChild className="mb-3 -ml-2">
        <Link to="/app/products"><ArrowLeft className="w-4 h-4 mr-1" /> Catalog</Link>
      </Button>
      <PageHeader title={p.product_name} subtitle={`${p.brand} · ${p.category} · SKU ${p.sku}`} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <SectionCard className="lg:col-span-1">
          <div className="aspect-square rounded-xl overflow-hidden bg-muted mb-3">
            <img src={p.image_url} alt={p.product_name} className="w-full h-full object-cover" />
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="aspect-square rounded-lg overflow-hidden bg-muted border border-border opacity-70 hover:opacity-100 transition">
                <img src={p.image_url} alt="" className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        </SectionCard>

        <div className="lg:col-span-2 space-y-4">
          <SectionCard>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-3xl font-semibold tracking-tight tabular-nums">₹{p.selling_price.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground line-through tabular-nums">₹{p.mrp.toLocaleString()}</div>
                <div className="flex items-center gap-3 mt-3">
                  <div className="flex items-center gap-1 text-sm"><Star className="w-4 h-4 fill-warning text-warning" />{p.rating}</div>
                  <span className="text-xs text-muted-foreground">{p.review_count.toLocaleString()} reviews</span>
                  <Badge variant="secondary">{p.warehouse}</Badge>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-muted-foreground">Current stock</div>
                <div className="text-2xl font-semibold tabular-nums">{p.current_stock}</div>
                <div className="text-xs text-muted-foreground">Safety {p.safety_stock} · Reorder {p.reorder_point}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
              {[
                ["Return rate", `${(p.return_rate * 100).toFixed(1)}%`],
                ["Defect rate", `${(p.defect_rate * 100).toFixed(1)}%`],
                ["Turnover", `${p.inventory_turnover}x`],
                ["Warranty", `${p.warranty_months}mo`],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl border border-border p-3">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{k}</div>
                  <div className="text-base font-semibold mt-1 tabular-nums">{v}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title="AI recommendations"
            actions={<Sparkles className="w-4 h-4 text-primary" />}
          >
            <ul className="space-y-2 text-sm">
              <li className="flex gap-2"><span className="text-primary">•</span> Increase safety stock at Mumbai WH by 25% — demand pulse rising next 14d.</li>
              <li className="flex gap-2"><span className="text-primary">•</span> Switch primary supplier to Quantum Components — projected saving ₹{(p.manufacturing_cost * 0.08 * 100).toFixed(0)}.</li>
              <li className="flex gap-2"><span className="text-primary">•</span> Bundle with compatible {p.category === "Headphones" ? "audio cable" : "accessory"} — historical attach rate 34%.</li>
            </ul>
          </SectionCard>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <SectionCard title="Sales trend" subtitle="Last 30 days">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={revenueTrend.slice(0, 30)}>
                <defs>
                  <linearGradient id="pdSales" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Area type="monotone" dataKey="orders" stroke="var(--color-chart-1)" strokeWidth={2} fill="url(#pdSales)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard title="Forecast" subtitle="Next 8 weeks">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastSeries}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Line dataKey="actual" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
                <Line dataKey="forecast" stroke="var(--color-chart-3)" strokeWidth={2} strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Supplier comparison" subtitle="Multiple suppliers ranked by AI" actions={<Badge variant="secondary">3 active</Badge>}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {linked.map((s, i) => {
            const Icon = s.badgeIcon;
            return (
              <motion.div
                key={s.supplier_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`relative rounded-2xl border p-5 transition-all hover:shadow-elevated ${
                  i === 0 ? "border-primary/40 bg-gradient-to-br from-primary/8 to-transparent" : "border-border bg-card"
                }`}
              >
                <div className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 mb-3 ${s.badgeColor}`}>
                  <Icon className="w-3 h-3" /> {s.badge}
                </div>
                <div className="font-semibold">{s.supplier_name}</div>
                <div className="text-xs text-muted-foreground">{s.city} · {s.supplier_specialization}</div>
                <div className="mt-4 space-y-2 text-sm">
                  <Row k="Reliability" v={`${(s.reliability_score * 100).toFixed(0)}%`} />
                  <Row k="Lead time" v={`${s.avg_lead_time_days}d`} />
                  <Row k="Defect rate" v={`${(s.defect_rate * 100).toFixed(2)}%`} />
                  <Row k="On-time" v={`${(s.on_time_delivery_rate * 100).toFixed(0)}%`} />
                  <Row k="Landed cost" v={`₹${s.landed_cost.toLocaleString()}`} />
                </div>
                <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
                  <div>
                    <div className="text-[10px] text-muted-foreground">AI score</div>
                    <div className="text-lg font-semibold text-primary">{(s.ai_score * 100).toFixed(0)}</div>
                  </div>
                  <Button size="sm" variant={i === 0 ? "default" : "outline"} className={i === 0 ? "gradient-primary text-primary-foreground border-0" : ""}>
                    Place PO
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>
      </SectionCard>
    </>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium tabular-nums">{v}</span>
    </div>
  );
}

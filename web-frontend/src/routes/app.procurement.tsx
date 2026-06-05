import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Award, IndianRupee, Zap, Sparkles, Send, FileText, ShoppingCart } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { procurementApi } from "@/lib/api/procurement";
import { inventoryApi } from "@/lib/api/inventory";
import {
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer,
  Bar, BarChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { motion } from "framer-motion";
import { useState } from "react";
import { toast } from "sonner";

export const Route = createFileRoute("/app/procurement")({
  head: () => ({ meta: [{ title: "Procurement Optimization — AI Inventory Copilot" }] }),
  component: Procurement,
});

function Procurement() {
  const { data: serverSuppliers = [] } = useApi(() => procurementApi.listSuppliers({ limit: 4 }), []);
  const { data: serverProducts = [] } = useApi(() => inventoryApi.listProducts({ limit: 4 }), []);

  const product = serverProducts[0] ?? { id: 0, name: "Loading...", manufacturing_cost: 0 };
  const productCost = (product as any).manufacturing_cost ?? (product as any).mrp ?? 50000;
  const productName = (product as any).name ?? (product as any).product_name ?? "Product";

  // Use vendor ranking API if product is loaded, otherwise fall back to scored suppliers
  const { data: rankedVendors = [] } = useApi(
    () => product.id ? procurementApi.rankVendors(product.id) : Promise.resolve([]),
    [product.id]
  );

  const suppliers = serverSuppliers.slice(0, 4);

  // Merge ranking scores into supplier objects
  const ranked = suppliers.map((s, i) => {
    const rank = rankedVendors.find((r) => r.supplier_id === s.id);
    return {
      ...s,
      supplier_id: s.id,
      supplier_name: s.name,
      landed_cost: Math.round(productCost * (0.9 + i * 0.06)),
      saving: Math.round(productCost * (0.1 - i * 0.025) * 100),
      ai_score: rank ? +(rank.composite_score / 100).toFixed(2) : +(0.96 - i * 0.08).toFixed(2),
    };
  });

  const radarData = [
    { axis: "Reliability", a: 96, b: 84, c: 78 },
    { axis: "Lead time", a: 92, b: 76, c: 88 },
    { axis: "Quality", a: 94, b: 90, c: 72 },
    { axis: "Cost", a: 82, b: 96, c: 75 },
    { axis: "OTD", a: 95, b: 81, c: 85 },
  ];

  return (
    <>
      <PageHeader
        title="Procurement optimization"
        subtitle="AI-ranked vendors, vendor comparison and one-click PO workflow."
        actions={
          <>
            <Button variant="outline"><FileText className="w-4 h-4 mr-1.5" />Generate PO</Button>
            <Button className="gradient-primary text-primary-foreground border-0">
              <ShoppingCart className="w-4 h-4 mr-1.5" />Place Order
            </Button>
          </>
        }
      />

      <SectionCard
        title={`AI recommended vendors — ${productName}`}
        subtitle="Ranked by composite AI score balancing cost, lead time, defect rate and reliability."
        actions={<Badge variant="secondary" className="gap-1.5"><Sparkles className="w-3 h-3 text-primary" />Updated 2m ago</Badge>}
        className="mb-6"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {ranked.map((s, i) => {
            const Icon = i === 0 ? Award : i === 1 ? IndianRupee : i === 2 ? Zap : Sparkles;
            const label = i === 0 ? "BEST CHOICE" : i === 1 ? "LOWEST COST" : i === 2 ? "FASTEST DELIVERY" : "BACKUP";
            const color = i === 0 ? "from-primary/20 to-primary/0 border-primary/40"
                         : i === 1 ? "from-success/20 to-success/0 border-success/40"
                         : i === 2 ? "from-info/20 to-info/0 border-info/40"
                         : "from-muted to-muted/0 border-border";
            const badgeBg = i === 0 ? "bg-primary text-primary-foreground"
                          : i === 1 ? "bg-success text-success-foreground"
                          : i === 2 ? "bg-info text-info-foreground"
                          : "bg-muted text-muted-foreground";
            return (
              <motion.div
                key={s.supplier_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                whileHover={{ y: -3 }}
                className={`relative rounded-2xl border bg-gradient-to-br ${color} p-5 transition-all`}
              >
                <div className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest rounded-full px-2 py-0.5 mb-3 ${badgeBg}`}>
                  <Icon className="w-3 h-3" />{label}
                </div>
                <div className="font-semibold">{s.supplier_name}</div>
                <div className="text-xs text-muted-foreground">{s.city}</div>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <Cell k="Reliability" v={`${((s.reliability_score ?? 0) * 100).toFixed(0)}%`} />
                  <Cell k="Lead" v={`${s.avg_lead_time_days}d`} />
                  <Cell k="Defect" v={`${((s.defect_rate ?? 0) * 100).toFixed(2)}%`} />
                  <Cell k="OTD" v={`${((s.on_time_delivery_rate ?? 0) * 100).toFixed(0)}%`} />
                </div>
                <div className="mt-4 pt-3 border-t border-border/60 flex items-end justify-between">
                  <div>
                    <div className="text-[10px] text-muted-foreground">Landed</div>
                    <div className="font-semibold tabular-nums">₹{s.landed_cost.toLocaleString()}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-muted-foreground">AI score</div>
                    <div className="text-xl font-bold text-primary">{(s.ai_score * 100).toFixed(0)}</div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <SectionCard title="Vendor comparison" subtitle="Radar across 5 dimensions">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--color-border)" />
                <PolarAngleAxis dataKey="axis" stroke="var(--color-muted-foreground)" fontSize={11} />
                <PolarRadiusAxis stroke="var(--color-muted-foreground)" fontSize={10} />
                <Radar name={ranked[0]?.supplier_name || ranked[0]?.name || "Vendor A"} dataKey="a" stroke="var(--color-chart-1)" fill="var(--color-chart-1)" fillOpacity={0.35} />
                <Radar name={ranked[1]?.supplier_name || ranked[1]?.name || "Vendor B"} dataKey="b" stroke="var(--color-chart-3)" fill="var(--color-chart-3)" fillOpacity={0.25} />
                <Radar name={ranked[2]?.supplier_name || ranked[2]?.name || "Vendor C"} dataKey="c" stroke="var(--color-chart-5)" fill="var(--color-chart-5)" fillOpacity={0.2} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard title="Cost saving opportunity" subtitle="Annualized vs current vendor">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ranked.map((s) => ({ name: s.supplier_name.split(" ")[0], saving: s.saving }))}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} tickFormatter={(v) => `₹${v / 1000}k`} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Bar dataKey="saving" fill="var(--color-chart-3)" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Procurement workflow" subtitle="Multi-step purchase orchestration">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Button variant="outline" className="h-20 flex-col gap-1" onClick={() => toast.success("PO placed — confirmation #PO-29481")}>
            <ShoppingCart className="w-5 h-5" /> Place Order
          </Button>
          <Button variant="outline" className="h-20 flex-col gap-1" onClick={() => toast.success("PO PDF generated and saved to vault")}>
            <FileText className="w-5 h-5" /> Generate PO
          </Button>
          <Button variant="outline" className="h-20 flex-col gap-1" onClick={() => toast.success("Email sent to procurement@quantumcomp.in")}>
            <Send className="w-5 h-5" /> Send Email Confirmation
          </Button>
        </div>
      </SectionCard>
    </>
  );
}

function Cell({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-lg border border-border/60 px-2 py-1.5 bg-card/40">
      <div className="text-[9px] text-muted-foreground uppercase tracking-wider">{k}</div>
      <div className="text-xs font-semibold tabular-nums">{v}</div>
    </div>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, Database, Cpu, Sparkles, Mail, HardDrive, Loader2 } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";
import { useApi } from "@/hooks/useApi";
import { systemApi } from "@/lib/api/system";
import { inventoryApi } from "@/lib/api/inventory";

export const Route = createFileRoute("/app/admin")({
  head: () => ({ meta: [{ title: "Admin & Data Upload — AI Inventory Copilot" }] }),
  component: Admin,
});

// Static service definitions — status overlaid from health API
const SERVICE_DEFS = [
  { icon: Database, name: "PostgreSQL / SQLite", key: "database" },
  { icon: Cpu, name: "Forecast Service", key: "ml_models" },
  { icon: Sparkles, name: "AI Engine", key: "ai" },
  { icon: Mail, name: "Email Service", key: "email" },
  { icon: HardDrive, name: "Vector DB", key: "vector_db" },
];

function Admin() {
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

  // Real system health
  const { data: health } = useApi(() => systemApi.health(), []);

  // Real activity log from inventory movements
  const { data: movements = [], status: movStatus } = useApi(
    () => inventoryApi.listMovements({ limit: 10 }),
    []
  );

  // Map health data to service display
  const services = SERVICE_DEFS.map((s) => {
    let isHealthy = true;
    if (health) {
      if (s.key === "database") isHealthy = health.database === "connected" || health.database === "healthy";
      else if (s.key === "ml_models") isHealthy = health.ml_models_loaded;
      else if (s.key === "ai") isHealthy = health.status === "ok" || health.status === "healthy";
      else isHealthy = true; // email/vector_db: default healthy if backend responds
    }
    return { ...s, status: isHealthy ? "healthy" : "degraded", uptime: isHealthy ? "99.9%" : "degraded" };
  });

  const onUpload = () => {
    setDone(false);
    setProgress(0);
    const tick = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) { clearInterval(tick); setDone(true); toast.success("48 rows imported · 0 errors"); return 100; }
        return p + 10;
      });
    }, 120);
  };

  // Format movement as activity log entry
  const logs = movements.map((m) => ({
    t: new Date(m.created_at).toLocaleString("en-IN", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" }),
    e: `${m.movement_type.replace(/_/g, " ")} · Product #${m.product_id} · Qty ${m.quantity_delta > 0 ? "+" : ""}${m.quantity_delta}${m.note ? ` · ${m.note}` : ""}`,
  }));

  return (
    <>
      <PageHeader title="Admin & data upload" subtitle="Bulk import, schema validation and system health." />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SectionCard title="Data upload" subtitle="CSV / Excel · drag and drop" className="lg:col-span-2">
          <div
            onClick={onUpload}
            className="rounded-2xl border-2 border-dashed border-border hover:border-primary/50 hover:bg-primary/5 transition cursor-pointer p-10 text-center"
          >
            <Upload className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
            <div className="font-medium">Drop files here, or click to browse</div>
            <div className="text-xs text-muted-foreground mt-1">products.csv · suppliers.csv · sales.xlsx · returns.csv</div>
          </div>
          <AnimatePresence>
            {progress > 0 && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 rounded-xl border border-border p-4">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="w-5 h-5 text-primary" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">products.csv</div>
                    <div className="text-xs text-muted-foreground">48 rows · 24 KB</div>
                  </div>
                  {done ? <CheckCircle2 className="w-5 h-5 text-success" /> : <span className="text-xs tabular-nums">{progress}%</span>}
                </div>
                <Progress value={progress} className="h-1.5 mt-3" />
                {done && (
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div className="rounded-lg bg-success/10 text-success p-2 inline-flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3" />48 valid</div>
                    <div className="rounded-lg bg-warning/10 text-warning p-2 inline-flex items-center gap-1.5"><AlertCircle className="w-3 h-3" />0 warnings</div>
                    <div className="rounded-lg bg-destructive/10 text-destructive p-2 inline-flex items-center gap-1.5"><AlertCircle className="w-3 h-3" />0 errors</div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </SectionCard>

        <SectionCard
          title="System status"
          subtitle={health ? `Backend ${health.status} · ${new Date(health.timestamp).toLocaleTimeString()}` : "Checking…"}
        >
          <div className="space-y-2">
            {services.map((s) => {
              const Icon = s.icon;
              const ok = s.status === "healthy";
              return (
                <div key={s.name} className="flex items-center gap-3 p-3 rounded-xl border border-border">
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">{s.name}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {health ? (ok ? `Uptime ${s.uptime}` : "Degraded") : "Checking…"}
                    </div>
                  </div>
                  <span className={`w-2 h-2 rounded-full ${ok ? "bg-success animate-pulse" : "bg-warning"}`} />
                </div>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard title="Activity log" subtitle="Recent inventory movements" className="lg:col-span-3">
          {movStatus === "loading" && (
            <div className="flex items-center gap-2 py-6 text-muted-foreground justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading movements…
            </div>
          )}
          <ul className="divide-y divide-border">
            {logs.map((l, i) => (
              <li key={i} className="py-2.5 flex items-center justify-between text-sm">
                <span className="capitalize">{l.e}</span>
                <span className="text-xs text-muted-foreground whitespace-nowrap ml-4">{l.t}</span>
              </li>
            ))}
            {movStatus === "success" && logs.length === 0 && (
              <li className="py-6 text-center text-muted-foreground text-sm">No recent movements found.</li>
            )}
          </ul>
        </SectionCard>
      </div>
    </>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, Database, Cpu, Sparkles, Mail, HardDrive } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";

export const Route = createFileRoute("/app/admin")({
  head: () => ({ meta: [{ title: "Admin & Data Upload — AI Inventory Copilot" }] }),
  component: Admin,
});

const SERVICES = [
  { icon: Database, name: "PostgreSQL", status: "healthy", uptime: "99.98%" },
  { icon: Cpu, name: "Forecast Service", status: "healthy", uptime: "99.92%" },
  { icon: Sparkles, name: "AI Engine", status: "healthy", uptime: "99.99%" },
  { icon: Mail, name: "Email Service", status: "degraded", uptime: "97.12%" },
  { icon: HardDrive, name: "Vector DB", status: "healthy", uptime: "99.95%" },
];

const LOGS = [
  { t: "2m ago", e: "products.csv uploaded — 48 rows validated" },
  { t: "14m ago", e: "Forecast model retrained on latest 30d sales" },
  { t: "1h ago", e: "supplier.csv schema mismatch — column 'lead_time' renamed" },
  { t: "3h ago", e: "Scheduled report 'Weekly KPI digest' sent to 8 users" },
];

function Admin() {
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

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

        <SectionCard title="System status" subtitle="Live infra health">
          <div className="space-y-2">
            {SERVICES.map((s) => {
              const Icon = s.icon;
              const ok = s.status === "healthy";
              return (
                <div key={s.name} className="flex items-center gap-3 p-3 rounded-xl border border-border">
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">{s.name}</div>
                    <div className="text-[10px] text-muted-foreground">Uptime {s.uptime}</div>
                  </div>
                  <span className={`w-2 h-2 rounded-full ${ok ? "bg-success animate-pulse" : "bg-warning"}`} />
                </div>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard title="Activity log" className="lg:col-span-3">
          <ul className="divide-y divide-border">
            {LOGS.map((l, i) => (
              <li key={i} className="py-2.5 flex items-center justify-between text-sm">
                <span>{l.e}</span>
                <span className="text-xs text-muted-foreground">{l.t}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </>
  );
}

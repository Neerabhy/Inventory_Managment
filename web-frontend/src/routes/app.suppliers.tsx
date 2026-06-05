import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { CITIES } from "@/lib/mock/data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, MapPin, Star, Sparkles, TrendingUp, Loader2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { useApi } from "@/hooks/useApi";
import { procurementApi } from "@/lib/api/procurement";

export const Route = createFileRoute("/app/suppliers")({
  head: () => ({ meta: [{ title: "Supplier Management — AI Inventory Copilot" }] }),
  component: Suppliers,
});

function Suppliers() {
  const [open, setOpen] = useState(false);
  const { data: suppliers = [], status, error } = useApi(() => procurementApi.listSuppliers(), []);

  return (
    <>
      <PageHeader
        title="Supplier management"
        subtitle="Onboard, score and benchmark suppliers across the network."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="gradient-primary text-primary-foreground border-0 shadow-glow">
                <Plus className="w-4 h-4 mr-1" /> Add Supplier
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-xl">
              <DialogHeader>
                <DialogTitle>Add new supplier</DialogTitle>
                <DialogDescription>Schema-aware onboarding with AI scoring preview.</DialogDescription>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Supplier name" className="col-span-2"><Input placeholder="Quantum Components Pvt" /></Field>
                <Field label="City">
                  <Select defaultValue="Mumbai">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{CITIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="Specialization">
                  <Select defaultValue="Laptops">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {["Laptops", "Smartphones", "Headphones", "Monitors", "Tablets", "Cameras"].map((c) =>
                        <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Avg lead time (days)"><Input type="number" defaultValue={7} /></Field>
                <Field label="Minimum order qty"><Input type="number" defaultValue={50} /></Field>
                <Field label="Payment terms">
                  <Select defaultValue="Net 30">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{["Net 15", "Net 30", "Net 45", "Net 60"].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="Country"><Input defaultValue="India" /></Field>
              </div>
              <div className="rounded-xl border border-primary/30 bg-gradient-to-br from-primary/8 to-transparent p-3 mt-2">
                <div className="flex items-center gap-1.5 text-xs font-medium mb-1">
                  <Sparkles className="w-3.5 h-3.5 text-primary" /> AI supplier score preview
                </div>
                <div className="text-2xl font-semibold text-primary">86 <span className="text-xs text-muted-foreground font-normal">/ 100</span></div>
                <div className="text-xs text-muted-foreground mt-1">Strong on cost & specialization. Lead time slightly above category median.</div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button
                  className="gradient-primary text-primary-foreground border-0"
                  onClick={() => { setOpen(false); toast.success("Supplier onboarded · ID auto-generated"); }}
                >Onboard supplier</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      {status === "loading" && (
        <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading suppliers…
        </div>
      )}
      {status === "error" && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center text-sm text-destructive">
          Failed to load suppliers: {error}
        </div>
      )}
      {status === "success" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {suppliers.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              whileHover={{ y: -3 }}
              className="rounded-2xl border border-border bg-card p-5 shadow-card hover:shadow-elevated transition-all"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold tracking-tight truncate">{s.name}</div>
                  <div className="text-xs text-muted-foreground inline-flex items-center gap-1 mt-0.5">
                    <MapPin className="w-3 h-3" />{s.city}{s.state ? `, ${s.state}` : ""}
                  </div>
                </div>
                <Badge variant="secondary" className="text-[10px]">{s.supplier_specialization ?? "General"}</Badge>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-4">
                <Cell k="Reliability" v={`${((s.reliability_score ?? 0) * 100).toFixed(0)}%`} good={(s.reliability_score ?? 0) > 0.85} />
                <Cell k="Defact Rate" v={`${s.defect_rate ?? "—"}d`} good={(s.defect_rate ?? 99) < 8} />
                <Cell k="On Time Delivery Rate" v={`${((s.on_time_delivery_rate ?? 0) * 100).toFixed(0)}%`} good={(s.on_time_delivery_rate ?? 0) > 0.9} />
              </div>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
                <div className="flex items-center gap-1 text-xs">
                  <Star className="w-3.5 h-3.5 fill-warning text-warning" />
                  <span className="font-medium">{((s.reliability_score ?? 0) * 5).toFixed(1)}</span>
                  <span className="text-muted-foreground">· {s.payment_terms ?? "N/A"}</span>
                </div>
                <Button size="sm" variant="ghost" className="text-primary"><TrendingUp className="w-3.5 h-3.5 mr-1" />Analyze</Button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </>
  );
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

function Cell({ k, v, good }: { k: string; v: string; good?: boolean }) {
  return (
    <div className="rounded-lg border border-border p-2">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{k}</div>
      <div className={`text-sm font-semibold tabular-nums ${good ? "text-success" : "text-foreground"}`}>{v}</div>
    </div>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { returns as initial, type ReturnItem } from "@/lib/mock/data";
import { Check, X, Sparkles, ShieldAlert, AlertCircle, CheckCircle2, ChevronRight } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

export const Route = createFileRoute("/app/returns/")({
  head: () => ({ meta: [{ title: "Returns Management — AI Inventory Copilot" }] }),
  component: Returns,
});

function Returns() {
  const [list, setList] = useState<ReturnItem[]>(initial.map((r) => ({ ...r })));
  const [selected, setSelected] = useState<string>(list[0]?.return_id ?? "");

  const update = (id: string, status: ReturnItem["approval_status"]) => {
    setList((l) => l.map((r) => (r.return_id === id ? { ...r, approval_status: status } : r)));
    toast.success(`${id} ${status}`);
  };
  const bulk = (predicate: (r: ReturnItem) => boolean, status: ReturnItem["approval_status"], label: string) => {
    setList((l) => l.map((r) => (predicate(r) && r.approval_status === "pending" ? { ...r, approval_status: status } : r)));
    toast.success(label);
  };

  const sel = list.find((r) => r.return_id === selected);

  return (
    <>
      <PageHeader
        title="Returns management"
        subtitle="AI-assisted return approval with explainability and fraud scoring."
        actions={
          <>
            <Button variant="outline" onClick={() => bulk((r) => r.ai_recommendation === "approve", "approved", "Approved all low-risk returns")}>
              <Check className="w-4 h-4 mr-1.5" /> Approve all low risk
            </Button>
            <Button variant="destructive" onClick={() => bulk((r) => r.fraud_risk_score > 0.7, "declined", "Rejected fraudulent returns")}>
              <X className="w-4 h-4 mr-1.5" /> Reject fraudulent
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Return</th>
                  <th className="px-4 py-3 font-medium">Customer</th>
                  <th className="px-4 py-3 font-medium">Fraud</th>
                  <th className="px-4 py-3 font-medium">Rev. cost</th>
                  <th className="px-4 py-3 font-medium">AI rec</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {list.map((r) => {
                  const isSelected = r.return_id === selected;
                  const recColor = r.ai_recommendation === "approve" ? "bg-success/10 text-success border-success/30"
                    : r.ai_recommendation === "decline" ? "bg-destructive/10 text-destructive border-destructive/30"
                    : "bg-warning/10 text-warning border-warning/30";
                  return (
                    <tr
                      key={r.return_id}
                      onClick={() => setSelected(r.return_id)}
                      className={`border-t border-border cursor-pointer transition ${isSelected ? "bg-primary/5" : "hover:bg-muted/30"}`}
                    >
                      <td className="px-4 py-3">
                        <div className="font-mono text-xs">{r.return_id}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[180px]">{r.product_name}</div>
                      </td>
                      <td className="px-4 py-3 text-xs">{r.customer_name}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Progress value={r.fraud_risk_score * 100} className="w-16 h-1.5" />
                          <span className="text-xs tabular-nums">{(r.fraud_risk_score * 100).toFixed(0)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs tabular-nums">₹{r.reverse_logistics_cost}</td>
                      <td className="px-4 py-3">
                        <span className={`text-[10px] uppercase tracking-wider rounded-md px-1.5 py-0.5 border ${recColor}`}>
                          {r.ai_recommendation === "manual_review" ? "Review" : r.ai_recommendation}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {r.approval_status === "pending" && <Badge variant="secondary">Pending</Badge>}
                        {r.approval_status === "approved" && <Badge className="bg-success text-success-foreground">Approved</Badge>}
                        {r.approval_status === "declined" && <Badge variant="destructive">Declined</Badge>}
                      </td>
                      <td className="px-4 py-3"><ChevronRight className="w-4 h-4 text-muted-foreground" /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <SectionCard title="AI explanation" actions={<Sparkles className="w-4 h-4 text-primary" />}>
          <AnimatePresence mode="wait">
            {sel && (
              <motion.div
                key={sel.return_id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                <div>
                  <div className="text-xs text-muted-foreground">Selected return</div>
                  <div className="font-mono text-sm">{sel.return_id} · ₹{sel.refund_amount.toLocaleString()}</div>
                </div>

                <div className="rounded-xl border border-border p-3 bg-gradient-to-br from-primary/5 to-transparent">
                  <div className="flex items-center gap-2 text-xs font-medium mb-1.5">
                    {sel.ai_recommendation === "approve" ? <CheckCircle2 className="w-4 h-4 text-success" />
                      : sel.ai_recommendation === "decline" ? <ShieldAlert className="w-4 h-4 text-destructive" />
                      : <AlertCircle className="w-4 h-4 text-warning" />}
                    Recommendation: {sel.ai_recommendation.replace("_", " ")}
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{sel.ai_reason}</p>
                </div>

                <div className="space-y-3 text-xs">
                  <Meter label="AI confidence" value={sel.ai_confidence * 100} color="bg-primary" />
                  <Meter label="Fraud risk" value={sel.fraud_risk_score * 100} color="bg-destructive" />
                  <Meter label="Cost / refund" value={(sel.reverse_logistics_cost / sel.refund_amount) * 100} color="bg-warning" />
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2">
                  <Button onClick={() => update(sel.return_id, "approved")} disabled={sel.approval_status === "approved"} className="bg-success text-success-foreground hover:bg-success/90">
                    <Check className="w-4 h-4 mr-1" />Approve
                  </Button>
                  <Button onClick={() => update(sel.return_id, "declined")} disabled={sel.approval_status === "declined"} variant="destructive">
                    <X className="w-4 h-4 mr-1" />Decline
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </SectionCard>
      </div>
    </>
  );
}

function Meter({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums">{value.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min(100, value)}%` }} transition={{ duration: 0.6 }} className={`h-full ${color}`} />
      </div>
    </div>
  );
}

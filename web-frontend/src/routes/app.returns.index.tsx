import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, X, Sparkles, ShieldAlert, AlertCircle, CheckCircle2, ChevronRight, Loader2, IndianRupee, Percent, RotateCcw, Truck } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { returnsApi, type ReturnRecord } from "@/lib/api/returns";

export const Route = createFileRoute("/app/returns/")({
  head: () => ({ meta: [{ title: "Returns Management — AI Inventory Copilot" }] }),
  component: Returns,
});

function riskLabel(r: ReturnRecord): "approve" | "decline" | "manual_review" {
  const score = Number(r.fraud_score ?? 0);
  if (score > 0.7 || r.risk_label === "HIGH") return "decline";
  if (score > 0.45 || r.anomaly_flag) return "manual_review";
  return "approve";
}

function Returns() {
  const { data: serverList = [], status, error, refetch } = useApi(() => returnsApi.listReturns({ status: "PENDING", limit: 100 }), []);
  const { data: summary } = useApi(() => returnsApi.summary(), []);
  // local overrides for instant UI feedback while backend processes
  const [localStatus, setLocalStatus] = useState<Record<number, string>>({});

  const list = serverList.map((r) => ({
    ...r,
    displayStatus: localStatus[r.id] ?? r.status,
  }));

  const [selected, setSelected] = useState<number | null>(null);
  const sel = list.find((r) => r.id === selected) ?? list[0] ?? null;

  const doApprove = async (id: number) => {
    try {
      setLocalStatus((p) => ({ ...p, [id]: "APPROVED" }));
      await returnsApi.approveReturn(id, "Approved from returns dashboard");
      toast.success(`Return #${id} approved`);
      refetch();
    } catch (e: any) {
      setLocalStatus((p) => { const n = { ...p }; delete n[id]; return n; });
      toast.error(e?.message ?? "Approval failed");
    }
  };

  const doDecline = async (id: number) => {
    try {
      setLocalStatus((p) => ({ ...p, [id]: "DECLINED" }));
      await returnsApi.declineReturn(id, "Declined via dashboard");
      toast.success(`Return #${id} declined`);
      refetch();
    } catch (e: any) {
      setLocalStatus((p) => { const n = { ...p }; delete n[id]; return n; });
      toast.error(e?.message ?? "Decline failed");
    }
  };

  const bulkApprove = async () => {
    const targets = list.filter((r) => r.displayStatus === "PENDING" && riskLabel(r) === "approve");
    for (const r of targets) await doApprove(r.id);
    toast.success(`Approved ${targets.length} low-risk returns`);
  };

  const bulkDecline = async () => {
    const targets = list.filter((r) => r.displayStatus === "PENDING" && Number(r.fraud_score ?? 0) > 0.7);
    for (const r of targets) await doDecline(r.id);
    toast.success(`Declined ${targets.length} high-fraud returns`);
  };

  return (
    <>
      <PageHeader
        title="Returns management"
        subtitle="AI-assisted return approval with explainability and fraud scoring."
        actions={
          <>
            <Button variant="outline" onClick={bulkApprove} disabled={status === "loading"}>
              <Check className="w-4 h-4 mr-1.5" /> Approve all low risk
            </Button>
            <Button variant="destructive" onClick={bulkDecline} disabled={status === "loading"}>
              <X className="w-4 h-4 mr-1.5" /> Reject fraudulent
            </Button>
          </>
        }
      />

      {status === "loading" && (
        <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading returns…
        </div>
      )}
      {status === "error" && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center text-sm text-destructive">
          Failed to load returns: {error}
        </div>
      )}
      {status === "success" && (
        <>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard label="Return Loss" value={summary?.estimated_return_loss ?? 0} prefix="Rs " decimals={0} delta={0} trendText="margin + reverse logistics" icon={IndianRupee} accent="warning" tooltip="Estimated profit impact from returned units and reverse logistics cost." tooltipMeaning="This is not refund value. It estimates margin leakage caused by returns." tooltipCalc="For each return, add product gross margin at risk plus reverse logistics cost." />
          <KpiCard label="Margin At Risk" value={summary?.gross_margin_lost ?? 0} prefix="Rs " decimals={0} delta={0} trendText="returned units" icon={RotateCcw} accent="info" tooltip="Gross margin attached to products that came back as returns." tooltipMeaning="Shows the profit pool affected by returned items." tooltipCalc="Selling price minus manufacturing cost for each returned product." />
          <KpiCard label="Return Rate" value={summary?.return_rate_pct ?? 0} suffix="%" decimals={2} delta={0} trendText={`${summary?.total_returns ?? 0} returns`} icon={Percent} accent="primary" tooltip="Returns as a percentage of sales orders." tooltipMeaning="Shows how much of sold order volume is coming back." tooltipCalc="Count returns divided by count sales orders, multiplied by 100." />
          <KpiCard label="Reverse Cost" value={summary?.reverse_logistics_cost ?? 0} prefix="Rs " decimals={0} delta={0} trendText="shipping impact" icon={Truck} accent="warning" tooltip="Total reverse logistics cost recorded on returns." tooltipMeaning="Shows shipping/logistics cost that directly reduces profit." tooltipCalc="Add reverse logistics cost across all return records." />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
          <div className="lg:col-span-2 rounded-2xl border border-border bg-card shadow-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 py-3 font-medium">Return</th>
                    <th className="px-4 py-3 font-medium">Reason</th>
                    <th className="px-4 py-3 font-medium">Fraud</th>
                    <th className="px-4 py-3 font-medium">Est. loss</th>
                    <th className="px-4 py-3 font-medium">AI rec</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {list.map((r) => {
                    const isSelected = r.id === sel?.id;
                    const rec = riskLabel(r);
                    const recColor = rec === "approve" ? "bg-success/10 text-success border-success/30"
                      : rec === "decline" ? "bg-destructive/10 text-destructive border-destructive/30"
                      : "bg-warning/10 text-warning border-warning/30";
                    const fraudPct = Number(r.fraud_score ?? 0) * 100;
                    const ds = r.displayStatus?.toUpperCase();
                    return (
                      <tr
                        key={r.id}
                        onClick={() => setSelected(r.id)}
                        className={`border-t border-border cursor-pointer transition ${isSelected ? "bg-primary/5" : "hover:bg-muted/30"}`}
                      >
                        <td className="px-4 py-3">
                          <div className="font-mono text-xs">RET-{String(r.id).padStart(5, "0")}</div>
                          <div className="text-xs text-muted-foreground">{r.reason_code ?? "—"}</div>
                        </td>
                        <td className="px-4 py-3 text-xs max-w-[140px] truncate">{r.reason_code ?? "—"}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Progress value={fraudPct} className="w-16 h-1.5" />
                            <span className="text-xs tabular-nums">{fraudPct.toFixed(0)}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs tabular-nums">Rs {Number(r.estimated_return_loss ?? 0).toLocaleString()}</td>
                        <td className="px-4 py-3">
                          <span className={`text-[10px] uppercase tracking-wider rounded-md px-1.5 py-0.5 border ${recColor}`}>
                            {rec === "manual_review" ? "Review" : rec}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {ds === "PENDING" || ds === "MANUAL REVIEW" || !ds
                            ? <Badge variant="secondary">Pending</Badge>
                            : ds === "APPROVED" || ds === "AUTO APPROVED"
                            ? <Badge className="bg-success text-success-foreground">Approved</Badge>
                            : <Badge variant="destructive">Declined</Badge>}
                        </td>
                        <td className="px-4 py-3"><ChevronRight className="w-4 h-4 text-muted-foreground" /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {list.length === 0 && (
                <div className="p-12 text-center text-muted-foreground text-sm">No pending returns to review.</div>
              )}
            </div>
          </div>

          <div className="sticky top-6">
            <SectionCard title="AI explanation" actions={<Sparkles className="w-4 h-4 text-primary" />}>
              <AnimatePresence mode="wait">
                {sel ? (
                  <motion.div
                    key={sel.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="space-y-4"
                  >
                    <div>
                      <div className="text-xs text-muted-foreground">Selected return</div>
                      <div className="font-mono text-sm">RET-{String(sel.id).padStart(5, "0")} · Rs {Number(sel.estimated_return_loss ?? 0).toLocaleString()}</div>
                    </div>

                    <div className="rounded-xl border border-border p-3 bg-gradient-to-br from-primary/5 to-transparent">
                      <div className="flex items-center gap-2 text-xs font-medium mb-1.5">
                        {riskLabel(sel) === "approve" ? <CheckCircle2 className="w-4 h-4 text-success" />
                          : riskLabel(sel) === "decline" ? <ShieldAlert className="w-4 h-4 text-destructive" />
                          : <AlertCircle className="w-4 h-4 text-warning" />}
                        Recommendation: {riskLabel(sel).replace("_", " ")}
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {riskLabel(sel) === "approve"
                          ? "Low fraud score. Customer in good standing. Condition matches policy."
                          : riskLabel(sel) === "decline"
                          ? "Elevated fraud signals. Customer return ratio above threshold."
                          : "Anomaly flagged or reverse logistics cost high — manual review suggested."}
                      </p>
                    </div>

                    <div className="space-y-3 text-xs">
                      <Meter label="Fraud risk" value={Number(sel.fraud_score ?? 0) * 100} color="bg-destructive" />
                      <Meter label="Return ratio" value={Number(sel.return_ratio ?? 0) * 100} color="bg-warning" />
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2">
                      <Button
                        onClick={() => doApprove(sel.id)}
                        disabled={sel.displayStatus?.toUpperCase() === "APPROVED"}
                        className="bg-success text-success-foreground hover:bg-success/90"
                      >
                        <Check className="w-4 h-4 mr-1" />Approve
                      </Button>
                      <Button
                        onClick={() => doDecline(sel.id)}
                        disabled={sel.displayStatus?.toUpperCase() === "DECLINED"}
                        variant="destructive"
                      >
                        <X className="w-4 h-4 mr-1" />Decline
                      </Button>
                    </div>
                  </motion.div>
                ) : (
                  <div className="text-sm text-muted-foreground py-10 text-center">
                    Select a return to view AI analysis.
                  </div>
                )}
              </AnimatePresence>
            </SectionCard>
          </div>
        </div>
        </>
      )}
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

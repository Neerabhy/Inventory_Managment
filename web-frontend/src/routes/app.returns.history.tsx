import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { useApi } from "@/hooks/useApi";
import { returnsApi } from "@/lib/api/returns";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, X, History as HistoryIcon, User, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";

export const Route = createFileRoute("/app/returns/history")({
  head: () => ({ meta: [{ title: "Return History — AI Inventory Copilot" }] }),
  component: ReturnHistory,
});

function ReturnHistory() {
  const { data: serverList = [], status, error, refetch } = useApi(() => returnsApi.getHistory({ limit: 100 }), []);

  const items = serverList.map((r) => ({
    ...r,
    // APPROVED and REAPPROVED both display as approved
    approval_status: (r.action?.toLowerCase() === "reapproved" ? "approved" : r.action?.toLowerCase()) ?? "pending",
    decided_by: r.approved_by && r.approved_by !== "ai_system" && r.approved_by !== "system_migration" ? "human" : "ai",
    human_override: !!r.override_note,
    decided_at: r.created_at
      ? r.created_at.substring(0, 16).replace("T", " ")
      : "",
    product_name: `Product #${r.product_id}`,
    customer_name: r.customer_id ? `Customer #${r.customer_id}` : "—",
    refund_amount: Number(r.refund_amount ?? 0),
    return_reason: r.reason_code ?? "Unknown",
    display_return_id: `RET-${String(r.return_id).padStart(5, "0")}`,
    raw_return_id: r.return_id,
  }));

  const reapprove = async (id: string | number, return_id: string | number) => {
    try {
      await returnsApi.approveReturn(Number(return_id), "Human override on rejected return");
      toast.success(`${id} re-approved with human override`);
      refetch();
    } catch (e: any) {
      toast.error(`Failed to re-approve: ${e.message}`);
    }
  };

  return (
    <>
      <PageHeader title="Return history" subtitle="Audit trail of approvals, AI vs human decisions, and overrides." />

      <SectionCard title="Audit timeline" actions={<HistoryIcon className="w-4 h-4 text-muted-foreground" />}>
        <ol className="relative border-l border-border ml-2">
          {items.map((r) => (
            <li key={r.id} className="mb-5 ml-6">
              <span className={`absolute -left-2.5 w-5 h-5 rounded-full grid place-items-center ring-4 ring-card ${
                r.approval_status === "approved" ? "bg-success" : "bg-destructive"
              }`}>
                {r.approval_status === "approved" ? <Check className="w-3 h-3 text-success-foreground" /> : <X className="w-3 h-3 text-destructive-foreground" />}
              </span>
              <div className="rounded-xl border border-border p-4 bg-card hover:shadow-card transition">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs">{r.display_return_id}</span>
                    {r.approval_status === "approved"
                      ? <Badge className="bg-success text-success-foreground">Approved</Badge>
                      : <Badge variant="destructive">Declined</Badge>}
                    {r.decided_by === "ai"
                      ? <Badge variant="secondary" className="gap-1"><Sparkles className="w-3 h-3" />AI</Badge>
                      : <Badge variant="outline" className="gap-1"><User className="w-3 h-3" />Human</Badge>}
                    {r.human_override && <Badge variant="outline" className="border-warning text-warning">Override</Badge>}
                  </div>
                  <span className="text-xs text-muted-foreground">{r.decided_at}</span>
                </div>
                <div className="text-sm mt-2">{r.product_name}</div>
                <div className="text-xs text-muted-foreground mt-1">{r.customer_name} · ₹{r.refund_amount.toLocaleString()} · {r.return_reason}</div>
                {r.approval_status === "declined" && (
                  <div className="mt-3">
                    <Button size="sm" variant="outline" onClick={() => reapprove(r.display_return_id, r.raw_return_id)}>
                      <Check className="w-3 h-3 mr-1" />Re-approve (override)
                    </Button>
                  </div>
                )}
                {r.approval_status === "approved" && (
                  <div className="text-[10px] text-muted-foreground mt-2 italic">Approved returns cannot be cancelled.</div>
                )}
              </div>
            </li>
          ))}
        </ol>
      </SectionCard>
    </>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { returns } from "@/lib/mock/data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, X, History as HistoryIcon, User, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";

export const Route = createFileRoute("/app/returns/history")({
  head: () => ({ meta: [{ title: "Return History — AI Inventory Copilot" }] }),
  component: ReturnHistory,
});

const HISTORY = returns.slice(0, 20).map((r, i) => ({
  ...r,
  approval_status: (i % 3 === 0 ? "declined" : "approved") as "approved" | "declined",
  decided_by: i % 4 === 0 ? "human" : "ai",
  human_override: i % 7 === 0,
  decided_at: `2026-05-${String(((i % 16) + 1)).padStart(2, "0")} 14:${String((i * 7) % 60).padStart(2, "0")}`,
}));

function ReturnHistory() {
  const [items, setItems] = useState(HISTORY);
  const reapprove = (id: string) => {
    setItems((l) => l.map((r) => (r.return_id === id ? { ...r, approval_status: "approved" as const, human_override: true, decided_by: "human" } : r)));
    toast.success(`${id} re-approved with human override`);
  };

  return (
    <>
      <PageHeader title="Return history" subtitle="Audit trail of approvals, AI vs human decisions, and overrides." />

      <SectionCard title="Audit timeline" actions={<HistoryIcon className="w-4 h-4 text-muted-foreground" />}>
        <ol className="relative border-l border-border ml-2">
          {items.map((r) => (
            <li key={r.return_id} className="mb-5 ml-6">
              <span className={`absolute -left-2.5 w-5 h-5 rounded-full grid place-items-center ring-4 ring-card ${
                r.approval_status === "approved" ? "bg-success" : "bg-destructive"
              }`}>
                {r.approval_status === "approved" ? <Check className="w-3 h-3 text-success-foreground" /> : <X className="w-3 h-3 text-destructive-foreground" />}
              </span>
              <div className="rounded-xl border border-border p-4 bg-card hover:shadow-card transition">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs">{r.return_id}</span>
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
                    <Button size="sm" variant="outline" onClick={() => reapprove(r.return_id)}>
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

import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, FileText, Mail, Calendar, BarChart3, Boxes, Truck, Building2 } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

export const Route = createFileRoute("/app/reports")({
  head: () => ({ meta: [{ title: "Reports & Analytics — AI Inventory Copilot" }] }),
  component: Reports,
});

const REPORTS = [
  { icon: BarChart3, title: "KPI trend analytics", desc: "30-day operational KPI movements with anomaly flags." },
  { icon: Boxes, title: "Warehouse analytics", desc: "Per-warehouse stock, turnover and dwell time breakdown." },
  { icon: Building2, title: "Supplier scorecard", desc: "Ranked supplier performance across all categories." },
  { icon: Truck, title: "Logistics & SLA", desc: "Delivery time, delay buckets, damage and lane economics." },
];

function Reports() {
  const [emailOpen, setEmailOpen] = useState(false);
  return (
    <>
      <PageHeader title="Reports & analytics" subtitle="Build, schedule and distribute enterprise reports." actions={
        <>
          <Button variant="outline" onClick={() => setEmailOpen(true)}><Mail className="w-4 h-4 mr-1.5" />Preview email</Button>
          <Button className="gradient-primary text-primary-foreground border-0"><Calendar className="w-4 h-4 mr-1.5" />Schedule</Button>
        </>
      } />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {REPORTS.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.title} className="rounded-2xl border border-border bg-card p-5 shadow-card hover:shadow-elevated transition group">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary grid place-items-center"><Icon className="w-5 h-5" /></div>
                <div className="flex-1">
                  <div className="font-semibold">{r.title}</div>
                  <p className="text-sm text-muted-foreground mt-1">{r.desc}</p>
                  <div className="flex items-center gap-2 mt-3">
                    <Button size="sm" variant="outline" onClick={() => toast.success(`${r.title} · CSV downloaded`)}><Download className="w-3.5 h-3.5 mr-1" />CSV</Button>
                    <Button size="sm" variant="outline" onClick={() => toast.success(`${r.title} · PDF downloaded`)}><FileText className="w-3.5 h-3.5 mr-1" />PDF</Button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <SectionCard title="Report builder" subtitle="Drag & drop fields to compose a custom export">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="rounded-xl border border-dashed border-border p-4 min-h-32">
            <div className="text-xs font-medium mb-2">Available fields</div>
            {["Revenue", "Orders", "Returns", "Defect rate", "OTD %", "Stock level", "Forecast"].map((f) => (
              <Badge key={f} variant="secondary" className="m-0.5">{f}</Badge>
            ))}
          </div>
          <div className="rounded-xl border-2 border-dashed border-primary/40 p-4 min-h-32 bg-primary/5">
            <div className="text-xs font-medium mb-2">Selected fields</div>
            {["Revenue", "Orders", "OTD %"].map((f) => (
              <Badge key={f} className="m-0.5 gradient-primary text-primary-foreground border-0">{f}</Badge>
            ))}
          </div>
          <div className="rounded-xl border border-border p-4 min-h-32">
            <div className="text-xs font-medium mb-2">Output</div>
            <div className="text-sm text-muted-foreground">CSV · PDF · Email · Slack</div>
            <Button size="sm" className="mt-3 gradient-primary text-primary-foreground border-0" onClick={() => toast.success("Custom report generated")}>Generate</Button>
          </div>
        </div>
      </SectionCard>

      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Email preview</DialogTitle></DialogHeader>
          <div className="rounded-xl border border-border bg-muted/30 p-4 text-sm">
            <div className="text-xs text-muted-foreground">To: ops-leads@company.com</div>
            <div className="text-xs text-muted-foreground">Subject: Weekly KPI digest — W19</div>
            <hr className="my-3 border-border" />
            <p>Hi team,</p>
            <p className="mt-2">Revenue is up 12.4% WoW. Return rate trending down (-0.4pp). Two supplier SLA breaches flagged for review.</p>
            <p className="mt-2">Full report attached as PDF.</p>
            <p className="mt-3 text-muted-foreground">— AI Inventory Copilot</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailOpen(false)}>Close</Button>
            <Button className="gradient-primary text-primary-foreground border-0" onClick={() => { setEmailOpen(false); toast.success("Email sent to 8 recipients"); }}>Send now</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

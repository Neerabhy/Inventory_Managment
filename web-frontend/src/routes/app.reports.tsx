import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Download,
  FileText,
  BarChart3,
  Boxes,
  Truck,
  Building2,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";
import { reportsApi, type ReportType } from "@/lib/api/reports";

export const Route = createFileRoute("/app/reports")({
  head: () => ({ meta: [{ title: "Reports & Analytics - AI Inventory Copilot" }] }),
  component: Reports,
});

const REPORTS = [
  {
    type: "executive" as const,
    icon: BarChart3,
    title: "KPI trend analytics",
    desc: "30-day operational KPI movements with anomaly flags.",
  },
  {
    type: "inventory" as const,
    icon: Boxes,
    title: "Warehouse analytics",
    desc: "Per-warehouse stock, turnover and stock-risk breakdown.",
  },
  {
    type: "forecast" as const,
    icon: TrendingUp,
    title: "Sales forecast report",
    desc: "Expected demand by date with analyst-ready product forecast rows.",
  },
  {
    type: "supplier" as const,
    icon: Building2,
    title: "Supplier scorecard",
    desc: "Ranked supplier performance across delivery, quality and reliability.",
  },
  {
    type: "logistics" as const,
    icon: Truck,
    title: "Logistics & SLA",
    desc: "Delivery time, delay buckets, shipment status and lane performance.",
  },
];

function Reports() {
  const [busy, setBusy] = useState<string | null>(null);

  const download = async (reportType: ReportType, format: "html" | "csv") => {
    setBusy(`${reportType}-${format}`);
    try {
      await reportsApi.download(reportType, format);
      toast.success(`${format.toUpperCase()} report downloaded`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Report download failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        title="Reports & analytics"
        subtitle="Download database-backed reports with useful charts and analyst-ready rows."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {REPORTS.map((r) => {
          const Icon = r.icon;
          return (
            <div
              key={r.title}
              className="rounded-2xl border border-border bg-card p-5 shadow-card transition"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary grid place-items-center">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <div className="font-semibold">{r.title}</div>
                  <p className="text-sm text-muted-foreground mt-1">{r.desc}</p>
                  <div className="flex flex-wrap items-center gap-2 mt-3">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy === `${r.type}-csv`}
                      onClick={() => download(r.type, "csv")}
                    >
                      <Download className="w-3.5 h-3.5 mr-1" />
                      CSV
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy === `${r.type}-html`}
                      onClick={() => download(r.type, "html")}
                    >
                      <FileText className="w-3.5 h-3.5 mr-1" />
                      Report
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <SectionCard
        title="Report templates"
        subtitle="Forecast template includes a chart and detailed forecast table"
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-muted/20 p-4 min-h-32">
            <div className="text-xs font-medium mb-2">Sales forecast fields</div>
            {[
              "Product",
              "SKU",
              "Forecast date",
              "Expected demand",
              "Low/high case",
              "Stockout days",
            ].map((f) => (
              <Badge key={f} variant="secondary" className="m-0.5">
                {f}
              </Badge>
            ))}
          </div>
          <div className="rounded-xl border border-border bg-muted/20 p-4 min-h-32">
            <div className="text-xs font-medium mb-2">Included in HTML</div>
            {["KPI cards", "Expected demand chart", "Detailed rows"].map((f) => (
              <Badge key={f} className="m-0.5 gradient-primary text-primary-foreground border-0">
                {f}
              </Badge>
            ))}
          </div>
          <div className="rounded-xl border border-border bg-muted/20 p-4 min-h-32">
            <div className="text-xs font-medium mb-2">Quick action</div>
            <div className="text-sm text-muted-foreground">
              Generate the forecast report for analysis.
            </div>
            <Button
              size="sm"
              className="mt-3 gradient-primary text-primary-foreground border-0"
              onClick={() => download("forecast", "html")}
            >
              Generate forecast report
            </Button>
          </div>
        </div>
      </SectionCard>

    </>
  );
}

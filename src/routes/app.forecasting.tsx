import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { forecastSeries } from "@/lib/mock/data";
import {
  Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sparkles } from "lucide-react";

export const Route = createFileRoute("/app/forecasting")({
  head: () => ({ meta: [{ title: "Demand Forecasting — AI Inventory Copilot" }] }),
  component: Forecasting,
});

function Forecasting() {
  const metrics = [
    { k: "MAE", v: "12.4", d: "lower is better" },
    { k: "RMSE", v: "18.7", d: "lower is better" },
    { k: "Forecast Confidence", v: "92%", d: "model agreement" },
    { k: "Demand Growth", v: "+9.2%", d: "next 30 days" },
  ];
  return (
    <>
      <PageHeader
        title="Demand forecasting"
        subtitle="AI-powered demand prediction with seasonality decomposition and confidence intervals."
        actions={
          <>
            <Select defaultValue="all">
              <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                <SelectItem value="lap">Laptops</SelectItem>
                <SelectItem value="hp">Headphones</SelectItem>
              </SelectContent>
            </Select>
            <Button className="gradient-primary text-primary-foreground border-0"><Sparkles className="w-4 h-4 mr-1" />Run forecast</Button>
          </>
        }
      />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {metrics.map((m) => (
          <div key={m.k} className="rounded-2xl border border-border bg-card p-5 shadow-card">
            <div className="text-xs text-muted-foreground">{m.k}</div>
            <div className="text-2xl font-semibold mt-1 tabular-nums">{m.v}</div>
            <div className="text-xs text-muted-foreground mt-1">{m.d}</div>
          </div>
        ))}
      </div>
      <SectionCard title="Forecast with confidence interval" subtitle="Historical actuals vs probabilistic forecast">
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={forecastSeries}>
              <defs>
                <linearGradient id="confBand" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-chart-3)" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="var(--color-chart-3)" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="week" stroke="var(--color-muted-foreground)" fontSize={11} />
              <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area dataKey="upper" stroke="none" fill="url(#confBand)" />
              <Area dataKey="lower" stroke="none" fill="var(--color-background)" />
              <Line dataKey="actual" stroke="var(--color-chart-1)" strokeWidth={2.5} dot={false} name="Actual" />
              <Line dataKey="forecast" stroke="var(--color-chart-3)" strokeWidth={2.5} strokeDasharray="6 4" dot={false} name="Forecast (P50)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <SectionCard title="Seasonality decomposition" subtitle="Trend · Seasonal · Residual">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastSeries}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12 }} />
                <Line dataKey="actual" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard title="AI commentary" actions={<Sparkles className="w-4 h-4 text-primary" />}>
          <ul className="space-y-3 text-sm">
            <li className="rounded-xl border border-border p-3"><b>Headphones</b> — demand will peak W19 (+24%) driven by Diwali campaigns. Pre-position 1.2k units.</li>
            <li className="rounded-xl border border-border p-3"><b>Laptops</b> — soft demand W17-18 (-7%). Hold POs; rebalance toward gaming SKUs.</li>
            <li className="rounded-xl border border-border p-3"><b>Smartphones</b> — confidence interval widens after W22 due to launch uncertainty.</li>
          </ul>
        </SectionCard>
      </div>
    </>
  );
}

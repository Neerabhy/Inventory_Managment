import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { useApi } from "@/hooks/useApi";
import { analyticsApi } from "@/lib/api/analytics";
import { copilotApi } from "@/lib/api/copilot";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  CalendarClock,
  Loader2,
  IndianRupee,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/app/forecasting")({
  head: () => ({ meta: [{ title: "Demand Forecasting - AI Inventory Copilot" }] }),
  component: Forecasting,
});

function Forecasting() {
  const [warehouse, setWarehouse] = useState<string>("all");
  const [category, setCategory] = useState<string>("all");
  const [period, setPeriod] = useState<string>("weeks");
  const [isRunningForecast, setIsRunningForecast] = useState(false);

  const { data: forecastSeries = [], refetch } = useApi(
    () =>
      analyticsApi.getForecastSeries({
        warehouse: warehouse === "all" ? undefined : warehouse,
        category: category === "all" ? undefined : category,
        period,
      }),
    [warehouse, category, period],
  );
  const { data: forecastInsights } = useApi(
    () =>
      copilotApi.getForecastInsights({
        warehouse: warehouse === "all" ? undefined : warehouse,
        category: category === "all" ? undefined : category,
        period,
      }),
    [warehouse, category, period],
  );

  const runForecast = async () => {
    setIsRunningForecast(true);
    try {
      const result = await analyticsApi.runForecast(true);
      toast.success(
        result.ran
          ? `Forecast refreshed for ${result.products_processed ?? 0} products`
          : (result.reason ?? "Forecast already up to date"),
      );
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to run forecast";
      toast.error(message);
    } finally {
      setIsRunningForecast(false);
    }
  };

  const periodLabel = period === "days" ? "day" : period === "months" ? "month" : "week";
  const nextPeriodLabel =
    period === "days" ? "next day" : period === "months" ? "next month" : "next week";
  const actualPoints = forecastSeries.filter((f) => f.actual !== null);
  const forecastPoints = forecastSeries.filter((f) => f.actual === null && f.forecast !== null);
  const latestActualPoint = actualPoints.at(-1);
  const latestActualBucket = latestActualPoint
    ? normalizeForecastLabel(latestActualPoint.date)
    : undefined;
  const nextForecastPoint =
    period === "days"
      ? forecastPoints[0]
      : (forecastPoints.find((point) =>
          latestActualBucket
            ? normalizeForecastLabel(point.date) > latestActualBucket
            : true,
        ) ??
        forecastPoints[0]);
  const recentSalesRevenue = latestActualPoint?.actualRevenue ?? 0;
  const forecastRevenue = nextForecastPoint?.forecastRevenue ?? 0;
  const recentAverage = recentSalesRevenue;
  const forecastAverage = forecastRevenue;
  const growthPct =
    recentAverage > 0 ? ((forecastAverage - recentAverage) / recentAverage) * 100 : 0;
  const peakRevenue = actualPoints.reduce(
    (max, point) => Math.max(max, point.actualRevenue ?? 0),
    0,
  );
  const peakPoint = actualPoints.find((point) => (point.actualRevenue ?? 0) === peakRevenue);

  const metrics = [
    {
      label: "Forecast Revenue",
      value: forecastRevenue,
      prefix: "Rs ",
      suffix: undefined,
      decimals: 0,
      trendText: nextForecastPoint?.date ?? nextPeriodLabel,
      icon: IndianRupee,
      accent: "primary" as const,
      tooltip: `Expected sales value for the ${nextPeriodLabel}.`,
      tooltipMeaning:
        "Use this to understand the immediate revenue expectation for the selected warehouse and category.",
      tooltipCalc:
        "For the next forecast period, multiply expected units by selling price for each product, then add the values together.",
    },
    {
      label: "Recent Sales Revenue",
      value: recentSalesRevenue,
      prefix: "Rs ",
      suffix: undefined,
      decimals: 0,
      trendText: latestActualPoint?.date ?? `latest ${periodLabel}`,
      icon: IndianRupee,
      accent: "info" as const,
      tooltip: `Actual sales value from the latest ${periodLabel} in the selected filters.`,
      tooltipMeaning:
        "This is the comparison point for the next forecast period.",
      tooltipCalc: `Add the final sale amount from customer orders in the latest ${periodLabel}.`,
    },
    {
      label: "Revenue Outlook",
      value: growthPct,
      prefix: undefined,
      suffix: "%",
      decimals: 1,
      trendText: `${nextPeriodLabel} vs latest ${periodLabel}`,
      icon: TrendingUp,
      accent: growthPct >= 0 ? ("success" as const) : ("warning" as const),
      tooltip: "Expected revenue movement compared with recent sales revenue.",
      tooltipMeaning:
        "Positive means the forecast is stronger than recent sales. Negative means revenue may soften.",
      tooltipCalc:
        "Compare next-period forecast revenue with the latest matching sales period, then show the difference as a percentage.",
    },
    {
      label: "Peak Revenue Period",
      value: peakRevenue,
      prefix: "Rs ",
      suffix: undefined,
      decimals: 0,
      trendText: peakPoint?.date ? peakPoint.date : "no history yet",
      icon: CalendarClock,
      accent: "warning" as const,
      tooltip: `Highest actual sales revenue in one past ${periodLabel}.`,
      tooltipMeaning:
        "This shows the strongest past revenue period in the selected filters, so the forecast can be compared against a real business benchmark.",
      tooltipCalc: `Find the past ${periodLabel} with the highest actual sales revenue.`,
    },
  ];

  return (
    <>
      <PageHeader
        title="Demand forecasting"
        subtitle="Sales history and expected demand for planning stock, campaigns, and purchase timing."
        actions={
          <div className="flex space-x-2">
            <Select value={warehouse} onValueChange={setWarehouse}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Warehouse" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All WH</SelectItem>
                <SelectItem value="1">Delhi (WH-1)</SelectItem>
                <SelectItem value="2">Mumbai (WH-2)</SelectItem>
                <SelectItem value="3">Bangalore (WH-3)</SelectItem>
              </SelectContent>
            </Select>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="Laptops">Laptops</SelectItem>
                <SelectItem value="Headphones">Headphones</SelectItem>
                <SelectItem value="Smartphones">Smartphones</SelectItem>
                <SelectItem value="Accessories">Accessories</SelectItem>
                <SelectItem value="Monitors">Monitors</SelectItem>
                <SelectItem value="Smartwatches">Smartwatches</SelectItem>
                <SelectItem value="Tablets">Tablets</SelectItem>
              </SelectContent>
            </Select>
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger className="w-28">
                <SelectValue placeholder="Period" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="days">Days</SelectItem>
                <SelectItem value="weeks">Weeks</SelectItem>
                <SelectItem value="months">Months</SelectItem>
              </SelectContent>
            </Select>
            <Button
              className="gradient-primary text-primary-foreground border-0"
              disabled={isRunningForecast}
              onClick={runForecast}
            >
              {isRunningForecast ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1" />
              )}
              {isRunningForecast ? "Running..." : "Run forecast"}
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {metrics.map((m) => (
          <KpiCard
            key={m.label}
            label={m.label}
            value={m.value}
            prefix={m.prefix}
            suffix={m.suffix}
            decimals={m.decimals}
            delta={0}
            trendText={m.trendText}
            icon={m.icon}
            tooltip={m.tooltip}
            tooltipMeaning={m.tooltipMeaning}
            tooltipCalc={m.tooltipCalc}
            accent={m.accent}
          />
        ))}
      </div>

      <SectionCard
        title="Sales revenue outlook"
        subtitle="Recent sales revenue compared with forecasted revenue"
      >
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={forecastSeries}>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" stroke="var(--color-muted-foreground)" fontSize={11} />
              <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: "var(--color-popover)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar
                dataKey="actualRevenue"
                fill="var(--color-chart-1)"
                radius={[4, 4, 0, 0]}
                name="Recent sales revenue"
              />
              <Line
                type="monotone"
                dataKey="forecastRevenue"
                stroke="var(--color-chart-3)"
                strokeWidth={2.5}
                dot={false}
                name="Forecast revenue"
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <SectionCard title="Recent sales movement" subtitle="Sales revenue over the selected period">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastSeries}>
                <CartesianGrid
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                  vertical={false}
                />
                <XAxis dataKey="date" stroke="var(--color-muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 12,
                  }}
                />
                <Line
                  dataKey="actualRevenue"
                  stroke="var(--color-chart-1)"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  name="Sales revenue"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard title="AI commentary" actions={<Sparkles className="w-4 h-4 text-primary" />}>
          <ul className="space-y-3 text-sm">
            {(
              forecastInsights?.insights ?? [
                "Prioritize stock for the products with the highest expected demand.",
                "Review low-stock products before approving campaigns.",
                "Compare expected demand with incoming inventory before placing new orders.",
              ]
            ).map((insight) => (
              <li key={insight} className="rounded-xl border border-border p-3">
                {insight}
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </>
  );
}

function normalizeForecastLabel(value: string) {
  return value.replace(" (Forecast)", "");
}

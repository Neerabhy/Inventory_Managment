import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { ArrowUp, ArrowDown, type LucideIcon } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

interface Props {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  delta: number;
  deltaLabel?: string;
  trendText?: string;
  icon: LucideIcon;
  tooltip: string;
  tooltipMeaning?: string;
  tooltipCalc?: string;
  sparkline?: { v: number }[];
  accent?: "primary" | "success" | "warning" | "destructive" | "info";
}

function useCounter(target: number, duration = 1200, when = true) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!when) return;
    let raf = 0;
    const start = performance.now();
    const step = (t: number) => {
      const p = Math.min((t - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      setV(target * ease);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, when]);
  return v;
}

export function KpiCard(props: Props) {
  const {
    label,
    value,
    prefix = "",
    suffix = "",
    decimals = 0,
    delta,
    deltaLabel = "vs last 30d",
    trendText,
    icon: Icon,
    tooltip,
    tooltipMeaning,
    tooltipCalc,
    sparkline,
    accent = "primary",
  } = props;
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });
  const animated = useCounter(value, 1400, inView);
  const positive = delta >= 0;

  const accentClass = {
    primary: "from-primary/15 to-primary/0 text-primary",
    success: "from-success/15 to-success/0 text-success",
    warning: "from-warning/15 to-warning/0 text-warning",
    destructive: "from-destructive/15 to-destructive/0 text-destructive",
    info: "from-info/15 to-info/0 text-info",
  }[accent];
  const tooltipAccentClass = {
    primary: "from-primary/20 via-primary/8 to-transparent border-primary/25 text-primary",
    success: "from-success/20 via-success/8 to-transparent border-success/25 text-success",
    warning: "from-warning/20 via-warning/8 to-transparent border-warning/25 text-warning",
    destructive:
      "from-destructive/20 via-destructive/8 to-transparent border-destructive/25 text-destructive",
    info: "from-info/20 via-info/8 to-transparent border-info/25 text-info",
  }[accent];

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <motion.div
            ref={ref}
            whileHover={{ y: -2 }}
            className="group relative overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-card hover:shadow-elevated transition-shadow"
          >
            <div
              className={`absolute inset-0 bg-gradient-to-br ${accentClass} opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none`}
            />
            <div className="relative flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                  {label}
                  <Info className="w-3 h-3 opacity-65 transition-opacity group-hover:opacity-100" />
                </div>
                <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
                  {prefix}
                  {animated.toLocaleString(undefined, {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals,
                  })}
                  {suffix}
                </div>
                {trendText ? (
                  <div className="mt-2 text-xs font-medium text-muted-foreground">{trendText}</div>
                ) : (
                  <div
                    className={`mt-2 inline-flex items-center gap-1 text-xs font-medium ${positive ? "text-success" : "text-destructive"}`}
                  >
                    {positive ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                    {Math.abs(delta).toFixed(1)}%{" "}
                    <span className="text-muted-foreground font-normal">{deltaLabel}</span>
                  </div>
                )}
              </div>
              <div
                className={`w-10 h-10 rounded-xl grid place-items-center bg-gradient-to-br ${accentClass} border border-border/50`}
              >
                <Icon className="w-5 h-5" />
              </div>
            </div>
            {sparkline && (
              <div className="relative h-12 mt-3 -mx-1">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparkline}>
                    <defs>
                      <linearGradient id={`spark-${label}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="v"
                      stroke="var(--color-primary)"
                      strokeWidth={1.6}
                      fill={`url(#spark-${label})`}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </motion.div>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          align="start"
          className="max-w-sm overflow-hidden border-border bg-popover p-0 shadow-elevated"
        >
          <div className={`border-b bg-gradient-to-br px-4 py-3 ${tooltipAccentClass}`}>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Icon className="h-4 w-4" />
              {label}
            </div>
            <div className="mt-1 text-xs text-foreground">{tooltip}</div>
          </div>
          <div className="space-y-3 p-4 text-xs">
            {tooltipMeaning && (
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-1 font-semibold text-foreground">Meaning</div>
                <div className="text-muted-foreground">{tooltipMeaning}</div>
              </div>
            )}
            {tooltipCalc && (
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-1 font-semibold text-foreground">How it is calculated</div>
                <div className="text-muted-foreground">{tooltipCalc}</div>
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

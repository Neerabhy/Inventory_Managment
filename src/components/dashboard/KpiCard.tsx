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
  const { label, value, prefix = "", suffix = "", decimals = 0, delta, icon: Icon, tooltip, tooltipMeaning, tooltipCalc, sparkline, accent = "primary" } = props;
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

  return (
    <TooltipProvider delayDuration={150}>
      <motion.div
        ref={ref}
        whileHover={{ y: -2 }}
        className="group relative overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-card hover:shadow-elevated transition-shadow"
      >
        <div className={`absolute inset-0 bg-gradient-to-br ${accentClass} opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none`} />
        <div className="relative flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
              {label}
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="opacity-60 hover:opacity-100"><Info className="w-3 h-3" /></button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-xs">
                  <div className="space-y-1.5 text-xs">
                    <div className="font-semibold">{tooltip}</div>
                    {tooltipMeaning && <div className="text-muted-foreground"><b>Why it matters:</b> {tooltipMeaning}</div>}
                    {tooltipCalc && <div className="text-muted-foreground"><b>How calculated:</b> {tooltipCalc}</div>}
                  </div>
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
              {prefix}
              {animated.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
              {suffix}
            </div>
            <div className={`mt-2 inline-flex items-center gap-1 text-xs font-medium ${positive ? "text-success" : "text-destructive"}`}>
              {positive ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
              {Math.abs(delta).toFixed(1)}% <span className="text-muted-foreground font-normal">vs last 30d</span>
            </div>
          </div>
          <div className={`w-10 h-10 rounded-xl grid place-items-center bg-gradient-to-br ${accentClass} border border-border/50`}>
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
                <Area type="monotone" dataKey="v" stroke="var(--color-primary)" strokeWidth={1.6} fill={`url(#spark-${label})`} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </motion.div>
    </TooltipProvider>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Send, TrendingUp, ShoppingCart, Truck, RotateCcw, Brain } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

export const Route = createFileRoute("/app/copilot")({
  head: () => ({ meta: [{ title: "AI Copilot — Supply Chain Assistant" }] }),
  component: Copilot,
});

interface Msg { role: "user" | "ai"; content: string; chart?: boolean; reasoning?: string[] }

const SUGGESTED = [
  "Why are monitor returns increasing?",
  "Forecast headphone demand next month",
  "Which supplier is best for laptops?",
];

const ENGINES = [
  { icon: TrendingUp, name: "Forecast Engine", status: "ready", color: "text-info" },
  { icon: ShoppingCart, name: "Procurement Analyzer", status: "ready", color: "text-primary" },
  { icon: Truck, name: "Logistics Analyzer", status: "ready", color: "text-warning" },
  { icon: RotateCcw, name: "Returns Intelligence", status: "ready", color: "text-success" },
];

function Copilot() {
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "ai", content: "Hi — I'm your operations copilot. Ask me about inventory, suppliers, forecasts or returns." },
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, typing]);

  const ask = (q: string) => {
    if (!q.trim()) return;
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setInput("");
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMsgs((m) => [...m, {
        role: "ai",
        content: q.toLowerCase().includes("forecast")
          ? "Headphone demand will peak in **W3** with a projected **+24%** lift. I'd pre-position 1,200 units across Mumbai (700) and Bangalore (500)."
          : q.toLowerCase().includes("supplier")
          ? "For laptops, **Quantum Components Pvt** ranks highest (AI score 92) with 95% on-time delivery and 0.8% defect rate. Switching saves ~₹42k/month."
          : "Monitor returns are up **18% MoM**. Root-cause analysis points to packaging changes from Apex Hardware after the Q1 supplier shift. I recommend an immediate audit.",
        chart: q.toLowerCase().includes("forecast") || q.toLowerCase().includes("returns"),
        reasoning: [
          "Pulled 30d historical sales for relevant category",
          "Ran seasonal decomposition + STL forecast",
          "Cross-referenced supplier reliability metrics",
          "Aggregated insights with confidence scoring",
        ],
      }]);
    }, 1200);
  };

  const chartData = [
    { w: "W1", v: 1200 }, { w: "W2", v: 1340 }, { w: "W3", v: 1820 }, { w: "W4", v: 1560 },
  ];

  return (
    <>
      <PageHeader title="AI Copilot" subtitle="Enterprise operations assistant with live tools and reasoning." actions={
        <span className="text-xs text-muted-foreground inline-flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" /> GPT-4 Turbo · Online
        </span>
      } />
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3 rounded-2xl border border-border bg-card shadow-card flex flex-col h-[calc(100vh-220px)]">
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <AnimatePresence initial={false}>
              {msgs.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}
                >
                  {m.role === "ai" && (
                    <div className="w-8 h-8 rounded-xl gradient-primary grid place-items-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-primary-foreground" />
                    </div>
                  )}
                  <div className={`max-w-xl rounded-2xl px-4 py-3 text-sm ${
                    m.role === "user" ? "gradient-primary text-primary-foreground" : "bg-muted/50 border border-border"
                  }`}>
                    <div className="whitespace-pre-wrap leading-relaxed" dangerouslySetInnerHTML={{ __html: m.content.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>") }} />
                    {m.chart && (
                      <div className="mt-3 h-40 rounded-lg bg-card/50 p-2">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={chartData}>
                            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="w" fontSize={10} stroke="var(--color-muted-foreground)" />
                            <YAxis fontSize={10} stroke="var(--color-muted-foreground)" />
                            <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 8 }} />
                            <Bar dataKey="v" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    {m.reasoning && (
                      <details className="mt-3 group">
                        <summary className="text-xs text-muted-foreground cursor-pointer inline-flex items-center gap-1"><Brain className="w-3 h-3" />Reasoning ({m.reasoning.length} steps)</summary>
                        <ol className="mt-2 ml-4 text-xs text-muted-foreground space-y-1 list-decimal">
                          {m.reasoning.map((r, j) => <li key={j}>{r}</li>)}
                        </ol>
                      </details>
                    )}
                  </div>
                </motion.div>
              ))}
              {typing && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                  <div className="w-8 h-8 rounded-xl gradient-primary grid place-items-center"><Sparkles className="w-4 h-4 text-primary-foreground" /></div>
                  <div className="bg-muted/50 border border-border rounded-2xl px-4 py-3 flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <div ref={endRef} />
          </div>
          <div className="border-t border-border p-4">
            <div className="flex flex-wrap gap-2 mb-3">
              {SUGGESTED.map((s) => (
                <button key={s} onClick={() => ask(s)} className="text-xs px-3 py-1.5 rounded-full border border-border hover:bg-muted transition">
                  {s}
                </button>
              ))}
            </div>
            <form onSubmit={(e) => { e.preventDefault(); ask(input); }} className="flex gap-2">
              <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask anything…" className="h-11 bg-muted/40" />
              <Button type="submit" className="h-11 gradient-primary text-primary-foreground border-0 shadow-glow"><Send className="w-4 h-4" /></Button>
            </form>
          </div>
        </div>

        <SectionCard title="AI engines" subtitle="Specialized tools">
          <div className="space-y-2">
            {ENGINES.map((e) => {
              const Icon = e.icon;
              return (
                <div key={e.name} className="flex items-center gap-3 p-3 rounded-xl border border-border hover:bg-muted/40 transition">
                  <Icon className={`w-4 h-4 ${e.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{e.name}</div>
                    <div className="text-[10px] text-muted-foreground inline-flex items-center gap-1">
                      <span className="w-1 h-1 rounded-full bg-success animate-pulse" /> {e.status}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      </div>
    </>
  );
}

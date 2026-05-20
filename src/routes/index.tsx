import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  Sparkles, ArrowRight, Boxes, ShoppingCart, Truck, RotateCcw, TrendingUp, Building2,
  ShieldCheck, Zap, BarChart3, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AI Inventory Copilot — AI Supply Chain Operating System" },
      { name: "description", content: "Premium AI-powered ERP and supply chain platform for electronics retail. Inventory, procurement, forecasting, logistics, and returns intelligence." },
    ],
  }),
  component: Landing,
});

const FEATURES = [
  { icon: Boxes, title: "Inventory Intelligence", desc: "Real-time SKU health, multi-warehouse stock visibility, safety-stock and reorder automation." },
  { icon: ShoppingCart, title: "Procurement Optimization", desc: "AI-ranked vendors balancing cost, lead time, defect rate and reliability." },
  { icon: Truck, title: "Logistics Analytics", desc: "Inbound and outbound shipment tracking with delay prediction across regions." },
  { icon: RotateCcw, title: "AI Return Approval", desc: "Auto-classify return requests by fraud risk, condition and reverse-logistics cost." },
  { icon: TrendingUp, title: "Forecasting Engine", desc: "Probabilistic demand forecasts with seasonality decomposition and confidence intervals." },
  { icon: Building2, title: "Supplier Intelligence", desc: "Onboard, score and benchmark suppliers with live performance signals." },
] as const;

const WORKFLOW = ["Suppliers", "Warehouses", "Orders", "Logistics", "Returns", "AI Insights"];

function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">
      {/* Nav */}
      <header className="sticky top-0 z-30 glass-strong border-b border-border">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 h-16 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl gradient-primary grid place-items-center shadow-glow">
              <Boxes className="w-5 h-5 text-primary-foreground" />
            </div>
            <div className="font-semibold tracking-tight">AI Inventory Copilot</div>
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-sm text-muted-foreground mx-8">
            <a href="#features" className="hover:text-foreground transition">Platform</a>
            <a href="#workflow" className="hover:text-foreground transition">Workflow</a>
            <a href="#enterprise" className="hover:text-foreground transition">Enterprise</a>
          </nav>
          <div className="flex-1" />
          <Button variant="ghost" asChild><Link to="/login">Sign in</Link></Button>
          <Button asChild className="gradient-primary text-primary-foreground border-0 shadow-glow">
            <Link to="/app/dashboard">Open Dashboard <ArrowRight className="w-4 h-4 ml-1" /></Link>
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="absolute inset-0 gradient-mesh opacity-70 pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,transparent,var(--color-background)_70%)] pointer-events-none" />
        <div className="relative max-w-7xl mx-auto px-6 lg:px-8 pt-20 pb-16 lg:pt-28 lg:pb-24">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-3xl"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 backdrop-blur px-3 py-1 text-xs text-muted-foreground mb-6">
              <Sparkles className="w-3.5 h-3.5 text-primary" />
              The AI operating system for retail supply chains
            </div>
            <h1 className="text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05]">
              <span className="text-foreground">AI Inventory </span>
              <span className="text-gradient">Copilot</span>
            </h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl leading-relaxed">
              AI-powered inventory, procurement, logistics, forecasting and returns intelligence — built for
              enterprise electronics retail operations across India.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" asChild className="gradient-primary text-primary-foreground border-0 shadow-glow h-12 px-6">
                <Link to="/app/dashboard">Open Dashboard <ArrowRight className="w-4 h-4 ml-1.5" /></Link>
              </Button>
              <Button size="lg" variant="outline" asChild className="h-12 px-6 backdrop-blur bg-card/40">
                <a href="#features">Explore Platform</a>
              </Button>
              <Button size="lg" variant="ghost" asChild className="h-12 px-6">
                <Link to="/app/copilot"><Sparkles className="w-4 h-4 mr-1.5" />Launch AI Copilot</Link>
              </Button>
            </div>
          </motion.div>

          {/* Floating dashboard preview */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="relative mt-16 lg:mt-20"
          >
            <div className="relative rounded-2xl border border-border bg-card/60 backdrop-blur-xl shadow-elevated overflow-hidden">
              <div className="flex items-center gap-1.5 px-4 h-9 border-b border-border bg-muted/30">
                <div className="w-2.5 h-2.5 rounded-full bg-destructive/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-warning/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-success/70" />
                <div className="ml-3 text-[11px] text-muted-foreground">ai-inventory-copilot.app/dashboard</div>
              </div>
              <div className="p-6 grid grid-cols-12 gap-4">
                <div className="col-span-12 md:col-span-8 grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { l: "Revenue", v: "₹4.82M", d: "+12.4%", c: "text-success" },
                    { l: "Orders", v: "12,408", d: "+8.1%", c: "text-success" },
                    { l: "Return Rate", v: "3.2%", d: "−0.4%", c: "text-success" },
                    { l: "Delayed", v: "31", d: "+6", c: "text-destructive" },
                  ].map((k) => (
                    <div key={k.l} className="rounded-xl border border-border bg-background/60 p-3">
                      <div className="text-[10px] text-muted-foreground">{k.l}</div>
                      <div className="text-base font-semibold mt-1 tracking-tight">{k.v}</div>
                      <div className={`text-[10px] mt-0.5 ${k.c}`}>{k.d}</div>
                    </div>
                  ))}
                  <div className="col-span-2 md:col-span-4 h-36 rounded-xl border border-border bg-background/60 p-3 relative overflow-hidden">
                    <div className="text-[10px] text-muted-foreground mb-2">Revenue trend · 30d</div>
                    <svg viewBox="0 0 400 100" className="absolute inset-x-3 bottom-2 w-[calc(100%-1.5rem)] h-24">
                      <defs>
                        <linearGradient id="heroSpark" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="oklch(0.72 0.18 265)" stopOpacity="0.4" />
                          <stop offset="100%" stopColor="oklch(0.72 0.18 265)" stopOpacity="0" />
                        </linearGradient>
                      </defs>
                      <path d="M0,70 C40,60 70,50 110,55 C160,62 200,30 250,32 C300,34 340,20 400,12 L400,100 L0,100 Z" fill="url(#heroSpark)" />
                      <path d="M0,70 C40,60 70,50 110,55 C160,62 200,30 250,32 C300,34 340,20 400,12" stroke="oklch(0.72 0.18 265)" strokeWidth="2" fill="none" />
                    </svg>
                  </div>
                </div>
                <div className="col-span-12 md:col-span-4 rounded-xl border border-border bg-background/60 p-4">
                  <div className="flex items-center gap-2 text-xs font-medium mb-3">
                    <Sparkles className="w-3.5 h-3.5 text-primary" /> AI Insights
                  </div>
                  <ul className="space-y-3 text-xs">
                    {[
                      "Monitor returns up 18% — logistics damage suspected.",
                      "Switch laptops to Quantum Components: save ₹42k/mo.",
                      "Headphone demand peaks W3 of next month (+24%).",
                    ].map((s) => (
                      <li key={s} className="flex gap-2">
                        <ChevronRight className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
                        <span className="text-muted-foreground">{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 lg:py-28">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="text-xs uppercase tracking-widest text-primary font-medium mb-3">Platform</div>
            <h2 className="text-3xl md:text-4xl font-semibold tracking-tight">A unified intelligence layer for every operation</h2>
            <p className="text-muted-foreground mt-4">Six AI-native modules, one operating system. Built for enterprise scale.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map((f, i) => {
              const Icon = f.icon;
              return (
                <motion.div
                  key={f.title}
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-50px" }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ y: -4 }}
                  className="group relative rounded-2xl border border-border bg-card p-6 shadow-card hover:shadow-elevated transition-all overflow-hidden"
                >
                  <div className="absolute inset-0 bg-gradient-to-br from-primary/8 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                  <div className="relative">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary/20 to-primary/0 border border-primary/20 grid place-items-center mb-4 group-hover:shadow-glow transition-shadow">
                      <Icon className="w-5 h-5 text-primary" />
                    </div>
                    <h3 className="font-semibold tracking-tight">{f.title}</h3>
                    <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{f.desc}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Workflow */}
      <section id="workflow" className="py-20 lg:py-28 relative">
        <div className="absolute inset-0 gradient-mesh opacity-50 pointer-events-none" />
        <div className="relative max-w-7xl mx-auto px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="text-xs uppercase tracking-widest text-primary font-medium mb-3">Workflow</div>
            <h2 className="text-3xl md:text-4xl font-semibold tracking-tight">End-to-end visibility, one canvas</h2>
            <p className="text-muted-foreground mt-4">From supplier dispatch to AI-driven insight — every event, ranked and explained.</p>
          </div>
          <div className="rounded-2xl border border-border glass-strong p-6 md:p-10">
            <div className="flex flex-wrap items-center justify-between gap-3">
              {WORKFLOW.map((s, i) => (
                <div key={s} className="flex items-center gap-3 flex-1 min-w-[120px]">
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                    className="flex-1 rounded-xl border border-border bg-card/60 px-4 py-3 text-center"
                  >
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Stage {i + 1}</div>
                    <div className="text-sm font-medium mt-1">{s}</div>
                  </motion.div>
                  {i < WORKFLOW.length - 1 && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      whileInView={{ opacity: 1 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.1 + 0.1 }}
                      className="hidden md:flex w-6 h-px bg-gradient-to-r from-primary/60 to-transparent relative"
                    >
                      <span className="absolute -top-1 right-0 w-2 h-2 rounded-full bg-primary animate-pulse" />
                    </motion.div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise band */}
      <section id="enterprise" className="py-20">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-5">
            {[
              { icon: ShieldCheck, t: "Enterprise security", d: "SOC 2, role-based access, audit logs across every action." },
              { icon: Zap, t: "Realtime by default", d: "Sub-second event streaming across warehouses and providers." },
              { icon: BarChart3, t: "Built for analysts", d: "Composable dashboards, exportable models, embedded AI." },
            ].map((b) => {
              const Icon = b.icon;
              return (
                <div key={b.t} className="rounded-2xl border border-border bg-card p-6">
                  <Icon className="w-5 h-5 text-primary mb-3" />
                  <div className="font-semibold">{b.t}</div>
                  <p className="text-sm text-muted-foreground mt-1.5">{b.d}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <footer className="border-t border-border py-10">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 flex flex-col md:flex-row gap-3 items-center justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md gradient-primary grid place-items-center">
              <Boxes className="w-3.5 h-3.5 text-primary-foreground" />
            </div>
            AI Inventory Copilot
          </div>
          <div>© 2026 Inventory Copilot Inc.</div>
        </div>
      </footer>
    </div>
  );
}

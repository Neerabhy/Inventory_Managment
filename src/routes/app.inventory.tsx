import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, Search, Filter, Boxes, ArrowUpDown } from "lucide-react";
import { products, CITIES, type Product } from "@/lib/mock/data";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { motion } from "framer-motion";

export const Route = createFileRoute("/app/inventory")({
  head: () => ({ meta: [{ title: "Inventory Management — AI Inventory Copilot" }] }),
  component: Inventory,
});

function statusBadge(p: Product) {
  if (p.current_stock < p.safety_stock) return <Badge variant="destructive">Low stock</Badge>;
  if (p.current_stock < p.reorder_point) return <Badge className="bg-warning text-warning-foreground hover:bg-warning/90">Reorder</Badge>;
  if (p.status === "discontinued") return <Badge variant="secondary">Discontinued</Badge>;
  return <Badge className="bg-success text-success-foreground hover:bg-success/90">Healthy</Badge>;
}

function Inventory() {
  const [q, setQ] = useState("");
  const [wh, setWh] = useState<string>("all");
  const [cat, setCat] = useState<string>("all");
  const [risk, setRisk] = useState<string>("all");
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    return products.filter((p) => {
      if (q && !`${p.product_name} ${p.sku} ${p.brand}`.toLowerCase().includes(q.toLowerCase())) return false;
      if (wh !== "all" && p.warehouse !== wh) return false;
      if (cat !== "all" && p.category !== cat) return false;
      if (risk === "low" && p.current_stock >= p.safety_stock) return false;
      if (risk === "reorder" && !(p.current_stock >= p.safety_stock && p.current_stock < p.reorder_point)) return false;
      if (risk === "healthy" && p.current_stock < p.reorder_point) return false;
      return true;
    });
  }, [q, wh, cat, risk]);

  const categories = Array.from(new Set(products.map((p) => p.category)));

  return (
    <>
      <PageHeader
        title="Inventory management"
        subtitle="Stock intelligence and operations across all warehouses."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="gradient-primary text-primary-foreground border-0 shadow-glow">
                <Plus className="w-4 h-4 mr-1" /> Add Product
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Add new product</DialogTitle>
                <DialogDescription>Schema-aware product creation. IDs and SKU auto-generated.</DialogDescription>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Product name"><Input placeholder="e.g. Sony WH-1000XM5" /></Field>
                <Field label="Brand"><Input placeholder="Sony" /></Field>
                <Field label="Category">
                  <Select defaultValue="Headphones">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="Warehouse">
                  <Select defaultValue="Mumbai">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{CITIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="MRP (₹)"><Input type="number" placeholder="29900" /></Field>
                <Field label="Selling price (₹)"><Input type="number" placeholder="24999" /></Field>
                <Field label="Manufacturing cost (₹)"><Input type="number" placeholder="14200" /></Field>
                <Field label="Safety stock"><Input type="number" placeholder="60" /></Field>
                <Field label="Reorder point"><Input type="number" placeholder="100" /></Field>
                <Field label="Supplier">
                  <Select defaultValue="S-001">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="S-001">Bharat Electronics Ltd</SelectItem>
                      <SelectItem value="S-002">Quantum Components Pvt</SelectItem>
                      <SelectItem value="S-003">NovaTech Distributors</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Image URL" className="col-span-2"><Input placeholder="https://…" /></Field>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button
                  className="gradient-primary text-primary-foreground border-0"
                  onClick={() => { setOpen(false); toast.success("Product created — SKU auto-generated, supplier linked."); }}
                >Create product</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <SectionCard className="mb-6">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search SKU, product, brand…" className="pl-9" />
          </div>
          <Select value={wh} onValueChange={setWh}>
            <SelectTrigger className="w-44"><SelectValue placeholder="Warehouse" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All warehouses</SelectItem>
              {CITIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={cat} onValueChange={setCat}>
            <SelectTrigger className="w-44"><SelectValue placeholder="Category" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={risk} onValueChange={setRisk}>
            <SelectTrigger className="w-44"><SelectValue placeholder="Stock risk" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All risk levels</SelectItem>
              <SelectItem value="low">Low stock</SelectItem>
              <SelectItem value="reorder">Reorder needed</SelectItem>
              <SelectItem value="healthy">Healthy</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon"><Filter className="w-4 h-4" /></Button>
        </div>
      </SectionCard>

      <div className="rounded-2xl border border-border bg-card shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 backdrop-blur z-10">
              <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Warehouse</th>
                <th className="px-4 py-3 font-medium text-right"><span className="inline-flex items-center gap-1">Stock <ArrowUpDown className="w-3 h-3" /></span></th>
                <th className="px-4 py-3 font-medium">Safety / Reorder</th>
                <th className="px-4 py-3 font-medium">Turnover</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => {
                const pct = Math.min(100, (p.current_stock / Math.max(1, p.reorder_point * 1.5)) * 100);
                const stockColor = p.current_stock < p.safety_stock ? "bg-destructive" : p.current_stock < p.reorder_point ? "bg-warning" : "bg-success";
                return (
                  <motion.tr
                    key={p.product_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.01 }}
                    className="border-t border-border hover:bg-muted/30 transition group"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover border border-border" />
                        <div className="min-w-0">
                          <Link to="/app/products/$sku" params={{ sku: p.sku }} className="font-medium hover:text-primary block truncate">{p.product_name}</Link>
                          <div className="text-xs text-muted-foreground">{p.brand} · {p.category}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{p.sku}</td>
                    <td className="px-4 py-3">{p.warehouse}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <div className="font-medium">{p.current_stock}</div>
                      <div className="w-24 h-1.5 bg-muted rounded-full ml-auto mt-1 overflow-hidden">
                        <div className={`h-full ${stockColor} transition-all`} style={{ width: `${pct}%` }} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{p.safety_stock} / {p.reorder_point}</td>
                    <td className="px-4 py-3 tabular-nums">{p.inventory_turnover}x</td>
                    <td className="px-4 py-3">{statusBadge(p)}</td>
                    <td className="px-4 py-3 text-right opacity-0 group-hover:opacity-100 transition">
                      <Button asChild size="sm" variant="ghost"><Link to="/app/products/$sku" params={{ sku: p.sku }}>View</Link></Button>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="p-12 text-center text-muted-foreground">
              <Boxes className="w-10 h-10 mx-auto opacity-30 mb-2" />
              No products match your filters.
            </div>
          )}
        </div>
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground">
          <div>Showing {filtered.length} of {products.length} SKUs</div>
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" disabled>Previous</Button>
            <Button size="sm" variant="ghost">Next</Button>
          </div>
        </div>
      </div>
    </>
  );
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { PageHeader } from "@/components/layout/Page";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, Star } from "lucide-react";
import { products } from "@/lib/mock/data";

export const Route = createFileRoute("/app/products/")({
  head: () => ({ meta: [{ title: "Product Catalog — AI Inventory Copilot" }] }),
  component: Catalog,
});

function Catalog() {
  const [q, setQ] = useState("");
  const list = products.filter((p) => !q || `${p.product_name} ${p.brand} ${p.sku}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageHeader title="Product catalog" subtitle="All SKUs across the network with live commercial signals." />
      <div className="relative max-w-md mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search catalog…" className="pl-9" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {list.map((p, i) => (
          <motion.div
            key={p.product_id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i * 0.02, 0.5) }}
            whileHover={{ y: -3 }}
          >
            <Link
              to="/app/products/$sku"
              params={{ sku: p.sku }}
              className="group block rounded-2xl border border-border bg-card overflow-hidden shadow-card hover:shadow-elevated transition-all"
            >
              <div className="aspect-square overflow-hidden bg-muted">
                <img src={p.image_url} alt={p.product_name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              </div>
              <div className="p-3">
                <div className="text-xs text-muted-foreground">{p.brand} · {p.category}</div>
                <div className="text-sm font-medium leading-tight mt-1 line-clamp-2 h-10">{p.product_name}</div>
                <div className="flex items-center justify-between mt-2">
                  <div className="text-sm font-semibold tabular-nums">₹{p.selling_price.toLocaleString()}</div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Star className="w-3 h-3 fill-warning text-warning" /> {p.rating}
                  </div>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <Badge variant="secondary" className="text-[10px]">{p.warehouse}</Badge>
                  <span className="text-[10px] text-muted-foreground">Stock: {p.current_stock}</span>
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </>
  );
}

import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { PageHeader } from "@/components/layout/Page";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, Star, Loader2 } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { inventoryApi } from "@/lib/api/inventory";
import { ProductImage } from "@/components/product/ProductImage";

export const Route = createFileRoute("/app/products/")({
  head: () => ({ meta: [{ title: "Product Catalog - AI Inventory Copilot" }] }),
  component: Catalog,
});

function Catalog() {
  const [q, setQ] = useState("");
  const { data: rawProducts = [], status } = useApi(
    () => inventoryApi.listProducts({ limit: 100 }),
    [],
  );

  const list = rawProducts.filter(
    (p) => !q || `${p.name} ${p.brand} ${p.sku}`.toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <>
      <PageHeader
        title="Product catalog"
        subtitle="All SKUs across the network with live commercial signals."
      />
      <div className="relative mb-6 max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search catalog..."
          className="pl-9"
        />
      </div>

      {status === "loading" && (
        <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading products...
        </div>
      )}

      {status === "success" && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {list.map((p, i) => {
            const records = p.inventory_records ?? [];
            const stock = records.reduce((sum, record) => sum + (record.quantity_on_hand ?? 0), 0);
            const warehouses = Array.from(
              new Set(records.map((record) => record.warehouse_city).filter(Boolean)),
            );
            const warehouseLabel =
              warehouses.length === 0
                ? "No warehouse"
                : warehouses.length === 1
                  ? warehouses[0]
                  : `${warehouses.length} warehouses`;

            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.5) }}
                whileHover={{ y: -3 }}
              >
                <Link
                  to="/app/products/$sku"
                  params={{ sku: p.sku }}
                  className="group block overflow-hidden rounded-xl border border-border bg-card shadow-card transition-all hover:shadow-elevated"
                >
                  <div className="flex h-44 items-center justify-center border-b border-border bg-white p-4 sm:h-48">
                    <ProductImage
                      src={p.image_url}
                      category={p.category}
                      alt={p.name}
                      className="h-full w-full transition-transform duration-500 group-hover:scale-[1.03]"
                    />
                  </div>
                  <div className="p-3">
                    <div className="text-xs text-muted-foreground">
                      {p.brand ?? "Brand"} · {p.category ?? "Category"}
                    </div>
                    <div className="mt-1 h-10 text-sm font-medium leading-tight line-clamp-2">
                      {p.name}
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <div className="text-sm font-semibold tabular-nums">
                        ₹{(p.selling_price ?? 0).toLocaleString()}
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Star className="h-3 w-3 fill-warning text-warning" /> {p.rating ?? 4.5}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <Badge variant="secondary" className="shrink-0 text-[10px]">
                        {warehouseLabel}
                      </Badge>
                      <span className="truncate text-[10px] text-muted-foreground">
                        Total stock: {stock.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      )}
    </>
  );
}

import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  Boxes,
  Package,
  TrendingUp,
  Truck,
  RotateCcw,
  Building2,
  Sparkles,
  BarChart3,
} from "lucide-react";

const ITEMS = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/app/inventory", label: "Inventory", icon: Boxes },
  { to: "/app/products", label: "Product Catalog", icon: Package },
  { to: "/app/forecasting", label: "Demand Forecasting", icon: TrendingUp },
  { to: "/app/logistics", label: "Logistics Tracking", icon: Truck },
  { to: "/app/returns", label: "Returns Management", icon: RotateCcw },
  { to: "/app/suppliers", label: "Suppliers", icon: Building2 },
  { to: "/app/copilot", label: "AI Copilot", icon: Sparkles },
  { to: "/app/reports", label: "Reports", icon: BarChart3 },
];

const AI_ACTIONS = [
  {
    label: "Check current sales performance",
    query: "How are sales going this month?",
  },
  {
    label: "Find low stock products",
    query: "Which products are low on stock and need attention?",
  },
  {
    label: "Forecast next-month demand",
    query: "Forecast demand for next month and explain the biggest risks.",
  },
  {
    label: "Review delayed shipments",
    query: "Which shipments are delayed and how many days late are they?",
  },
  {
    label: "Compare best suppliers",
    query: "Which suppliers are performing best and why?",
  },
];

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const nav = useNavigate();
  const openCopilotWithQuery = (query: string) => {
    window.sessionStorage.setItem("copilot_pending_query", query);
    onOpenChange(false);
    nav({ to: "/app/copilot" });
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Jump to page, run command, search…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {ITEMS.map((i) => {
            const Icon = i.icon;
            return (
              <CommandItem
                key={i.to}
                onSelect={() => {
                  onOpenChange(false);
                  nav({ to: i.to });
                }}
              >
                <Icon className="w-4 h-4 mr-2" />
                {i.label}
              </CommandItem>
            );
          })}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="AI Actions">
          <CommandItem
            onSelect={() => {
              onOpenChange(false);
              nav({ to: "/app/copilot" });
            }}
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Ask AI Copilot
          </CommandItem>
          <CommandItem
            onSelect={() => {
              onOpenChange(false);
              nav({ to: "/app/reports" });
            }}
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            Generate forecast report
          </CommandItem>
          {AI_ACTIONS.map((action) => (
            <CommandItem key={action.label} onSelect={() => openCopilotWithQuery(action.query)}>
              <Sparkles className="w-4 h-4 mr-2" />
              {action.label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

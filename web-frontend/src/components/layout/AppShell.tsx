import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Boxes,
  Package,
  TrendingUp,
  Truck,
  RotateCcw,
  History,
  Building2,
  Sparkles,
  BarChart3,
  ChevronLeft,
  Search,
  Bell,
  Sun,
  Moon,
  Command,
  CircleUser,
  LogOut,
  Boxes as Logo,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState, type ReactNode } from "react";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CopilotFab } from "./CopilotFab";
import { CommandPalette } from "./CommandPalette";
import { useApi } from "@/hooks/useApi";
import { inventoryApi } from "@/lib/api/inventory";
import { logisticsApi } from "@/lib/api/logistics";
import { returnsApi } from "@/lib/api/returns";

const NAV = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/app/inventory", label: "Inventory", icon: Boxes },
  { to: "/app/products", label: "Product Catalog", icon: Package },
  { to: "/app/forecasting", label: "Demand Forecasting", icon: TrendingUp },
  { to: "/app/logistics", label: "Logistics", icon: Truck },
  { to: "/app/returns", label: "Returns", icon: RotateCcw },
  { to: "/app/returns/history", label: "Return History", icon: History },
  { to: "/app/suppliers", label: "Suppliers", icon: Building2 },
  { to: "/app/copilot", label: "AI Copilot", icon: Sparkles },
  { to: "/app/reports", label: "Reports", icon: BarChart3 },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const displayName = user?.full_name || user?.username || "User";
  const initials =
    displayName
      .split(/\s+/)
      .map((s) => s[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "U";
  const role = (user?.roles && user.roles[0]) || user?.department || "Member";
  const { data: stockAlerts = [] } = useApi(() => inventoryApi.getStockAlerts(), []);
  const { data: returnSummary } = useApi(() => returnsApi.summary(), []);
  const { data: logisticsSummary } = useApi(() => logisticsApi.summary(), []);
  const notifications = [
    ...stockAlerts.slice(0, 2).map((alert) => ({
      t: "Low stock alert",
      d: `${alert.product_name} at ${alert.warehouse_city ?? `WH-${alert.warehouse_id}`} has ${alert.current_stock} units left`,
      c: "destructive",
      to: "/app/inventory" as const,
    })),
    ...(returnSummary && returnSummary.pending > 0
      ? [
          {
            t: "Returns pending",
            d: `${returnSummary.pending} returns need review, ${returnSummary.high_risk} high-risk`,
            c: returnSummary.high_risk > 0 ? "destructive" : "warning",
            to: "/app/returns" as const,
          },
        ]
      : []),
    ...(logisticsSummary && logisticsSummary.delayed_shipments > 0
      ? [
          {
            t: "Shipment delays",
            d: `${logisticsSummary.delayed_shipments} delayed shipments, ${logisticsSummary.delay_rate_pct}% delay rate`,
            c: "warning",
            to: "/app/logistics" as const,
          },
        ]
      : []),
  ].slice(0, 4);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

      {/* Sidebar */}
      <motion.aside
        animate={{ width: collapsed ? 76 : 264 }}
        transition={{ type: "spring", stiffness: 260, damping: 30 }}
        className="sticky top-0 h-screen flex-shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground flex flex-col overflow-hidden z-30"
      >
        <div className="flex items-center gap-3 px-4 h-16 border-b border-sidebar-border">
          <div className="w-9 h-9 rounded-xl gradient-primary grid place-items-center shadow-glow flex-shrink-0">
            <Logo className="w-5 h-5 text-primary-foreground" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                className="flex flex-col min-w-0"
              >
                <span className="font-semibold text-sm tracking-tight">AI Inventory</span>
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest">
                  Copilot
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV.map((item) => {
            const active =
              path === item.to || (item.to !== "/app/dashboard" && path.startsWith(item.to));
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-card"
                    : "text-sidebar-foreground/75 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                }`}
              >
                {active && (
                  <motion.div
                    layoutId="active-nav"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full gradient-primary"
                  />
                )}
                <Icon className="w-[18px] h-[18px] flex-shrink-0" />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="truncate"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-sidebar-border">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="w-full flex items-center justify-center gap-2 text-xs text-muted-foreground hover:text-foreground py-2 rounded-md hover:bg-sidebar-accent/50 transition"
          >
            <ChevronLeft
              className={`w-4 h-4 transition-transform ${collapsed ? "rotate-180" : ""}`}
            />
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </motion.aside>

      {/* Main column */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 h-16 border-b border-border glass-strong flex items-center gap-3 px-6">
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex items-center gap-2.5 flex-1 max-w-md text-sm text-muted-foreground bg-muted/40 hover:bg-muted transition rounded-lg px-3 py-2 border border-border"
          >
            <Search className="w-4 h-4" />
            <span className="flex-1 text-left">Search products, suppliers, orders…</span>
            <kbd className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded border border-border bg-background/50">
              <Command className="w-3 h-3" /> K
            </kbd>
          </button>

          <div className="flex-1" />

          <Button size="icon" variant="ghost" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon" variant="ghost" className="relative">
                <Bell className="w-4 h-4" />
                {notifications.length > 0 && (
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-destructive animate-pulse-glow" />
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
              <DropdownMenuLabel className="flex items-center justify-between">
                Notifications{" "}
                <Badge variant="secondary" className="text-[10px]">
                  {notifications.length} new
                </Badge>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {notifications.length === 0 && (
                <DropdownMenuItem className="text-xs text-muted-foreground">
                  No active operational alerts.
                </DropdownMenuItem>
              )}
              {notifications.map((n, i) => (
                <DropdownMenuItem
                  key={i}
                  className="flex flex-col items-start gap-1 py-2.5"
                  onClick={() => nav({ to: n.to })}
                >
                  <div className="flex items-center gap-2 w-full">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        n.c === "destructive"
                          ? "bg-destructive"
                          : n.c === "warning"
                            ? "bg-warning"
                            : "bg-success"
                      }`}
                    />
                    <span className="font-medium text-sm">{n.t}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">{n.d}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="gap-2 pl-2 pr-3">
                <div className="w-7 h-7 rounded-full gradient-primary grid place-items-center text-primary-foreground text-xs font-semibold">
                  {initials}
                </div>
                <div className="hidden sm:flex flex-col items-start">
                  <span className="text-xs font-medium leading-none">{displayName}</span>
                  <span className="text-[10px] text-muted-foreground">{role}</span>
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{user?.email || "My Account"}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <CircleUser className="w-4 h-4 mr-2" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem>Settings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => {
                  logout();
                  nav({ to: "/login" });
                }}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        <main className="flex-1 px-6 pb-6 pt-4 lg:px-8 lg:pb-8 lg:pt-5">
          <AnimatePresence mode="wait">
            <motion.div
              key={path}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>

        <CopilotFab />
      </div>
    </div>
  );
}

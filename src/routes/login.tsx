import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { Boxes, Mail, Lock, ArrowRight, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Sign in — AI Inventory Copilot" }, { name: "description", content: "Sign in to AI Inventory Copilot." }] }),
  component: Login,
});

function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState("sys.admin");
  const [password, setPassword] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
      toast.success("Signed in");
      nav({ to: "/app/dashboard" });
    } catch (err: any) {
      toast.error(err?.message || "Sign in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex relative overflow-hidden">
      <div className="absolute inset-0 gradient-mesh opacity-60 pointer-events-none" />

      {/* Left brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12 relative">
        <Link to="/" className="flex items-center gap-2.5 relative">
          <div className="w-10 h-10 rounded-xl gradient-primary grid place-items-center shadow-glow">
            <Boxes className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="font-semibold tracking-tight">AI Inventory Copilot</span>
        </Link>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="relative">
          <div className="text-4xl font-semibold tracking-tight leading-tight max-w-md">
            The AI operating system for <span className="text-gradient">supply chain operations</span>.
          </div>
          <p className="text-muted-foreground mt-4 max-w-md">
            Inventory, procurement, logistics, forecasting and returns intelligence — all unified, all in real time.
          </p>
        </motion.div>
        <div className="text-xs text-muted-foreground relative">© 2026 Inventory Copilot Inc.</div>
      </div>

      {/* Right form */}
      <div className="flex-1 grid place-items-center p-6 relative">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md glass-strong rounded-2xl shadow-elevated p-8"
        >
          <div className="lg:hidden flex items-center gap-2 mb-6">
            <div className="w-9 h-9 rounded-xl gradient-primary grid place-items-center"><Boxes className="w-4 h-4 text-primary-foreground" /></div>
            <span className="font-semibold">AI Inventory Copilot</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
          <p className="text-sm text-muted-foreground mt-1.5">Access your operations control center.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="username"
                  required
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-9 h-11 bg-background/50"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <button type="button" className="text-xs text-primary hover:underline">Forgot password?</button>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="password"
                  type={show ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-9 pr-9 h-11 bg-background/50"
                />
                <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox defaultChecked /> Remember me for 30 days
            </label>
            <Button type="submit" disabled={loading} className="w-full h-11 gradient-primary text-primary-foreground border-0 shadow-glow">
              {loading ? "Signing in…" : <>Sign in <ArrowRight className="w-4 h-4 ml-1.5" /></>}
            </Button>
          </form>

          <div className="mt-6 text-sm text-center text-muted-foreground">
            New here? <Link to="/signup" className="text-primary font-medium hover:underline">Create account</Link>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { Boxes, Mail, Lock, User, Building2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

export const Route = createFileRoute("/signup")({
  head: () => ({ meta: [{ title: "Create account — AI Inventory Copilot" }, { name: "description", content: "Create your AI Inventory Copilot account." }] }),
  component: Signup,
});

function Signup() {
  const nav = useNavigate();
  const [loading, setLoading] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      toast.success("Account created. Welcome!");
      nav({ to: "/app/dashboard" });
    }, 700);
  };
  return (
    <div className="min-h-screen bg-background text-foreground grid place-items-center p-6 relative overflow-hidden">
      <div className="absolute inset-0 gradient-mesh opacity-60 pointer-events-none" />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md glass-strong rounded-2xl shadow-elevated p-8 relative"
      >
        <Link to="/" className="flex items-center gap-2 mb-6">
          <div className="w-9 h-9 rounded-xl gradient-primary grid place-items-center"><Boxes className="w-4 h-4 text-primary-foreground" /></div>
          <span className="font-semibold">AI Inventory Copilot</span>
        </Link>
        <h1 className="text-2xl font-semibold">Create your account</h1>
        <p className="text-sm text-muted-foreground mt-1.5">Spin up your supply chain workspace in seconds.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div className="space-y-1.5">
            <Label>Full name</Label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input required className="pl-9 h-11 bg-background/50" placeholder="Aarav Kapoor" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Company</Label>
            <div className="relative">
              <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input required className="pl-9 h-11 bg-background/50" placeholder="Nova Electronics Retail" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Work email</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input type="email" required className="pl-9 h-11 bg-background/50" placeholder="you@company.com" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Password</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input type="password" required className="pl-9 h-11 bg-background/50" placeholder="At least 8 characters" />
            </div>
          </div>
          <Button type="submit" disabled={loading} className="w-full h-11 gradient-primary text-primary-foreground border-0 shadow-glow">
            {loading ? "Creating account…" : <>Create account <ArrowRight className="w-4 h-4 ml-1.5" /></>}
          </Button>
        </form>
        <div className="mt-6 text-sm text-center text-muted-foreground">
          Already have one? <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
        </div>
      </motion.div>
    </div>
  );
}

import { Sparkles, X, Send } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";

export function CopilotFab() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-2xl gradient-primary text-primary-foreground shadow-glow grid place-items-center animate-pulse-glow"
        aria-label="Open AI Copilot"
      >
        <Sparkles className="w-6 h-6" />
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
            className="fixed bottom-24 right-6 z-40 w-[360px] glass-strong rounded-2xl shadow-elevated overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-border flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg gradient-primary grid place-items-center">
                <Sparkles className="w-4 h-4 text-primary-foreground" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold">AI Copilot</div>
                <div className="text-[10px] text-muted-foreground flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" /> Online · GPT-4 Turbo
                </div>
              </div>
              <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-2 text-xs">
              <div className="text-muted-foreground">Try one of these:</div>
              {[
                "Why are monitor returns increasing?",
                "Forecast headphone demand next month",
                "Which supplier is best for laptops?",
              ].map((q) => (
                <Link
                  key={q}
                  to="/app/copilot"
                  onClick={() => setOpen(false)}
                  className="block px-3 py-2 rounded-lg bg-muted/50 hover:bg-muted transition border border-border/50"
                >
                  {q}
                </Link>
              ))}
            </div>
            <div className="p-3 border-t border-border flex gap-2">
              <input
                placeholder="Ask anything…"
                className="flex-1 bg-muted/50 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 ring-primary/40"
              />
              <Button size="icon" asChild>
                <Link to="/app/copilot"><Send className="w-4 h-4" /></Link>
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

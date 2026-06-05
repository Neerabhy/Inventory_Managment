import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Brain,
  RotateCcw,
  Send,
  ShoppingCart,
  Sparkles,
  TrendingUp,
  Truck,
} from "lucide-react";

import { PageHeader, SectionCard } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { openCopilotSocket, type CopilotStreamEvent } from "@/lib/api/copilot";
import { toast } from "sonner";

export const Route = createFileRoute("/app/copilot")({
  head: () => ({ meta: [{ title: "AI Copilot - Supply Chain Assistant" }] }),
  component: Copilot,
});

interface Msg {
  role: "user" | "ai";
  content: string;
  chartData?: { label: string; value: number }[];
  reasoning?: string[];
}

const SESSION_KEY = "copilot.session.messages";

const DEFAULT_MESSAGES: Msg[] = [
  {
    role: "ai",
    content:
      "Hi - I'm your operations copilot. Ask me about inventory, suppliers, forecasts or returns.",
  },
];

const FALLBACK_SUGGESTED = [
  "How are sales going this month?",
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
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    const restored = loadSessionMessages();
    return restored.length ? restored : DEFAULT_MESSAGES;
  });

  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [connected, setConnected] = useState(false);

  const endRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const activeRef = useRef<{
    aiIndex: number;
    text: string;
    chartData?: Msg["chartData"];
    reasoning: string[];
    usedDataFallback?: boolean;
    narrativeBuffer?: string;
  } | null>(null);

  const suggested = FALLBACK_SUGGESTED;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, typing]);

  useEffect(() => {
    saveSessionMessages(msgs);
  }, [msgs]);

  const updateActiveMessage = () => {
    const active = activeRef.current;
    if (!active) return;

    setMsgs((current) =>
      current.map((msg, index) =>
        index === active.aiIndex
          ? {
              ...msg,
              content: active.text,
              chartData: active.chartData,
              reasoning: [...active.reasoning],
            }
          : msg,
      ),
    );
  };

  const handleStreamEvent = (event: CopilotStreamEvent | null) => {
    if (
      !event ||
      event.type === "connection" ||
      event.type === "version" ||
      event.type === "received"
    ) {
      return;
    }

    const active = activeRef.current;
    if (!active) return;

    if (event.type === "intent" && event.content) {
      active.reasoning.push(`Intent detected: ${event.content}`);
      updateActiveMessage();
      return;
    }

    if (event.type === "tool_call" && event.content) {
      active.reasoning.push(event.content);
      updateActiveMessage();
      return;
    }

    if (event.type === "data" && event.content) {
      const parsed = parseDataContext(event.content);
      if (parsed?.chart && Array.isArray(parsed.chart)) {
        active.chartData = parsed.chart;
      }
      if (!active.text.trim()) {
        const fallback = summarizeDataContext(parsed);
        if (fallback) {
          active.text = fallback;
          active.usedDataFallback = true;
        }
      }
      updateActiveMessage();
      return;
    }

    if (event.type === "narrative" && event.content) {
      if (active.usedDataFallback) {
        active.narrativeBuffer = `${active.narrativeBuffer ?? ""}${event.content}`;
      } else {
        active.text += event.content;
      }
      updateActiveMessage();
      return;
    }

    if (event.type === "done") {
      if (active.usedDataFallback && active.narrativeBuffer?.trim()) {
        active.text = active.narrativeBuffer;
        active.usedDataFallback = false;
        updateActiveMessage();
      }
      activeRef.current = null;
      setTyping(false);
      return;
    }

    if (event.type === "error") {
      active.text = event.content || "Copilot stream failed.";
      active.reasoning.push("WebSocket stream returned an error");
      updateActiveMessage();
      toast.error(active.text);
      activeRef.current = null;
      setTyping(false);
    }
  };

  const connectSocket = () => {
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return wsRef.current;
    }

    const socket = openCopilotSocket();
    wsRef.current = socket;

    socket.onopen = () => {
      if (wsRef.current !== socket) return;
      setConnected(true);
    };

    socket.onclose = (event) => {
      if (wsRef.current !== socket) return;

      console.warn("Copilot WebSocket closed:", {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });

      setConnected(false);
      wsRef.current = null;
    };

    socket.onerror = (event) => {
      if (wsRef.current !== socket) return;

      console.error("Copilot WebSocket error:", event);
      setConnected(false);

      if (
        socket.readyState !== WebSocket.CLOSING &&
        socket.readyState !== WebSocket.CLOSED
      ) {
        toast.error("Copilot WebSocket connection failed");
      }
    };

    socket.onmessage = (message) => {
      if (wsRef.current !== socket) return;
      handleStreamEvent(parseStreamEvent(message.data));
    };

    return socket;
  };

  const ask = (raw: string) => {
    const query = raw.trim();
    if (!query || activeRef.current) return;

    const socket = connectSocket();

    setInput("");
    setTyping(true);

    setMsgs((current) => {
      const next = [
        ...current,
        { role: "user" as const, content: query },
        { role: "ai" as const, content: "", reasoning: [] },
      ];

      activeRef.current = {
        aiIndex: next.length - 1,
        text: "",
        reasoning: [],
        narrativeBuffer: "",
      };

      return next;
    });

    const payload = JSON.stringify({
      query,
      context: {},
    });

    if (socket.readyState === WebSocket.OPEN) {
      socket.send(payload);
      return;
    }

    if (socket.readyState === WebSocket.CONNECTING) {
      socket.addEventListener(
        "open",
        () => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(payload);
          }
        },
        { once: true },
      );
      return;
    }

    toast.error("Copilot WebSocket is not connected. Please try again.");
    activeRef.current = null;
    setTyping(false);
  };

  const clearChat = () => {
    activeRef.current = null;
    setTyping(false);
    setMsgs(DEFAULT_MESSAGES);
    window.sessionStorage.removeItem(SESSION_KEY);
  };

  useEffect(() => {
    return () => {
      const socket = wsRef.current;

      wsRef.current = null;
      activeRef.current = null;
      setTyping(false);
      setConnected(false);

      if (
        socket &&
        (socket.readyState === WebSocket.OPEN ||
          socket.readyState === WebSocket.CONNECTING)
      ) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close(1000, "Copilot page unmounted");
      }
    };
  }, []);

  useEffect(() => {
    const pendingQuery = window.sessionStorage.getItem("copilot_pending_query");
    if (!pendingQuery) return;

    window.sessionStorage.removeItem("copilot_pending_query");
    ask(pendingQuery);
  }, []);

  return (
    <>
      <PageHeader
        title="AI Copilot"
        subtitle="Enterprise operations assistant with live tools and streaming reasoning."
        actions={
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  connected ? "bg-success animate-pulse" : "bg-muted-foreground"
                }`}
              />
              {connected ? "WebSocket online" : "Connects when you ask"}
            </span>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={clearChat}
              disabled={typing}
            >
              Clear chat
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="flex h-[calc(100vh-220px)] flex-col rounded-2xl border border-border bg-card shadow-card lg:col-span-3">
          <div className="flex-1 space-y-4 overflow-y-auto p-6">
            <AnimatePresence initial={false}>
              {msgs.map((m, i) => {
                const isEmptyAiMessage =
                  m.role === "ai" &&
                  !m.content.trim() &&
                  (!m.chartData || m.chartData.length === 0);

                if (isEmptyAiMessage) return null;

                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}
                  >
                    {m.role === "ai" && (
                      <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-xl gradient-primary">
                        <Sparkles className="h-4 w-4 text-primary-foreground" />
                      </div>
                    )}

                    <div
                      className={`rounded-2xl px-4 py-3 text-sm ${
                        m.role === "user"
                          ? "max-w-xl gradient-primary text-primary-foreground"
                          : "max-w-[min(920px,calc(100%-3rem))] border border-border bg-muted/50"
                      }`}
                    >
                      {m.content.trim() && (
                        <div
                          className="copilot-markdown prose prose-sm max-w-none leading-relaxed dark:prose-invert"
                          dangerouslySetInnerHTML={{ __html: renderCopilotMarkdown(m.content) }}
                        />
                      )}

                      {m.chartData && m.chartData.length > 0 && (
                        <div className="mt-3 h-40 rounded-lg bg-card/50 p-2">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={m.chartData}>
                              <CartesianGrid
                                stroke="var(--color-border)"
                                strokeDasharray="3 3"
                                vertical={false}
                              />
                              <XAxis
                                dataKey="label"
                                fontSize={10}
                                stroke="var(--color-muted-foreground)"
                              />
                              <YAxis fontSize={10} stroke="var(--color-muted-foreground)" />
                              <Tooltip
                                contentStyle={{
                                  background: "var(--color-popover)",
                                  border: "1px solid var(--color-border)",
                                  borderRadius: 8,
                                }}
                              />
                              <Bar
                                dataKey="value"
                                fill="var(--color-chart-1)"
                                radius={[6, 6, 0, 0]}
                              />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      )}

                      {m.reasoning && m.reasoning.length > 0 && m.content.trim() && (
                        <details className="group mt-3">
                          <summary className="inline-flex cursor-pointer items-center gap-1 text-xs text-muted-foreground">
                            <Brain className="h-3 w-3" />
                            Reasoning ({m.reasoning.length} steps)
                          </summary>
                          <ol className="mt-2 ml-4 list-decimal space-y-1 text-xs text-muted-foreground">
                            {m.reasoning.map((r, j) => (
                              <li key={j}>{r}</li>
                            ))}
                          </ol>
                        </details>
                      )}
                    </div>
                  </motion.div>
                );
              })}

              {typing && !activeRef.current?.text && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-3"
                >
                  <div className="grid h-8 w-8 place-items-center rounded-xl gradient-primary">
                    <Sparkles className="h-4 w-4 text-primary-foreground" />
                  </div>
                  <div className="flex h-10 items-center gap-1 rounded-2xl border border-border bg-muted/50 px-4">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={endRef} />
          </div>

          <div className="border-t border-border p-4">
            <div className="mb-3 flex flex-wrap gap-2">
              {suggested.slice(0, 6).map((s) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs transition hover:bg-muted"
                  disabled={typing}
                >
                  {s}
                </button>
              ))}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask(input);
              }}
              className="flex gap-2"
            >
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything..."
                className="h-11 bg-muted/40"
              />
              <Button
                type="submit"
                disabled={typing}
                className="h-11 border-0 gradient-primary text-primary-foreground shadow-glow"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>

        <SectionCard title="AI engines" subtitle="Specialized tools">
          <div className="space-y-2">
            {ENGINES.map((e) => {
              const Icon = e.icon;

              return (
                <div
                  key={e.name}
                  className="flex items-center gap-3 rounded-xl border border-border p-3 transition hover:bg-muted/40"
                >
                  <Icon className={`h-4 w-4 ${e.color}`} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{e.name}</div>
                    <div className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                      <span className="h-1 w-1 rounded-full bg-success animate-pulse" />
                      {e.status}
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

function loadSessionMessages(): Msg[] {
  if (typeof window === "undefined") return [];

  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);

    if (!Array.isArray(parsed)) return [];

    return parsed.filter(
      (msg): msg is Msg =>
        msg &&
        (msg.role === "user" || msg.role === "ai") &&
        typeof msg.content === "string" &&
        (msg.role === "user" || msg.content.trim().length > 0),
    );
  } catch {
    return [];
  }
}

function saveSessionMessages(messages: Msg[]) {
  if (typeof window === "undefined") return;

  try {
    const cleaned = messages.filter(
      (msg) =>
        msg &&
        (msg.role === "user" || msg.role === "ai") &&
        typeof msg.content === "string" &&
        (msg.role === "user" || msg.content.trim().length > 0),
    );

    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(cleaned));
  } catch {
    // Ignore sessionStorage errors.
  }
}

function parseStreamEvent(value: unknown): CopilotStreamEvent | null {
  if (typeof value !== "string") return null;

  try {
    return JSON.parse(value) as CopilotStreamEvent;
  } catch {
    return null;
  }
}

type DataContext = {
  chart?: { label: string; value: number }[];
  rows?: Record<string, unknown>[];
  row_count?: number;
  error?: string;
};

function parseDataContext(value: string): DataContext | null {
  try {
    return JSON.parse(value) as DataContext;
  } catch {
    return null;
  }
}

function summarizeDataContext(data: DataContext | null) {
  if (!data) return "";
  if (data.error) return `I could not fetch database results. Reason: ${String(data.error)}`;

  const rows = Array.isArray(data.rows) ? data.rows : [];
  const rowCount = Number(data.row_count ?? rows.length);
  if (!rows.length) return "";

  const lines = [
    "**Summary**",
    `- Found **${rowCount} matching row${rowCount === 1 ? "" : "s"}** from live data.`,
    "",
    "**Top matches**",
    "| # | Product | SKU | Warehouse | Available | Days cover | Incoming |",
    "|---:|---|---|---|---:|---:|---:|",
  ];

  rows.slice(0, 10).forEach((row, index) => {
    const product = stringValue(row.product_name) || stringValue(row.sku) || "Product";
    const sku = stringValue(row.sku);
    const warehouse = stringValue(row.warehouse_city) || stringValue(row.warehouse_name);
    const available = numberValue(row.available_stock);
    const days = numberValue(row.estimated_days_until_stockout ?? row.stockout_in_days);
    const incoming = numberValue(row.incoming_stock);

    lines.push(
      `| ${index + 1} | ${product} | ${sku} | ${warehouse} | ${
        available ?? ""
      } | ${days ?? ""} | ${incoming ?? ""} |`,
    );
  });

  if (rowCount > 10) lines.push(`- ${rowCount - 10} more rows matched.`);
  return lines.join("\n");
}

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function numberValue(value: unknown) {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderMarkdown(value: string) {
  const escaped = escapeHtml(value);

  return escaped
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^### (.*)$/gm, "<strong>$1</strong>")
    .replace(/^[-*] (.*)$/gm, "&bull; $1")
    .replace(/^\d+\. (.*)$/gm, "$&")
    .replace(/^- (.*)$/gm, "• $1")
    .replace(/\n/g, "<br />");
}

function renderCopilotMarkdown(value: string) {
  const lines = value.split(/\r?\n/);
  const html: string[] = [];

  for (let i = 0; i < lines.length; i += 1) {
    if (isMarkdownTableStart(lines, i)) {
      const tableLines = [lines[i], lines[i + 1]];
      i += 2;
      while (i < lines.length && isTableRow(lines[i])) {
        tableLines.push(lines[i]);
        i += 1;
      }
      i -= 1;
      html.push(renderMarkdownTable(tableLines));
      continue;
    }

    const line = lines[i];
    if (!line.trim()) {
      html.push("<br />");
      continue;
    }
    html.push(renderMarkdownLine(line));
  }

  return html.join("");
}

function renderMarkdownLine(line: string) {
  const escaped = escapeHtml(line);
  if (/^###\s+/.test(line)) {
    return `<div class="mt-3 font-semibold">${inlineMarkdown(escaped.replace(/^###\s+/, ""))}</div>`;
  }
  if (/^[-*]\s+/.test(line)) {
    return `<div class="my-1 flex gap-2"><span class="text-muted-foreground">&bull;</span><span>${inlineMarkdown(
      escaped.replace(/^[-*]\s+/, ""),
    )}</span></div>`;
  }
  if (/^\d+\.\s+/.test(line)) {
    const match = escaped.match(/^(\d+)\.\s+(.*)$/);
    return `<div class="my-1 flex gap-2"><span class="text-muted-foreground">${match?.[1] ?? ""}.</span><span>${inlineMarkdown(
      match?.[2] ?? escaped,
    )}</span></div>`;
  }
  return `<div>${inlineMarkdown(escaped)}</div>`;
}

function inlineMarkdown(escaped: string) {
  return escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
}

function isTableRow(line: string) {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.split("|").length > 2;
}

function isTableSeparator(line: string) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
}

function isMarkdownTableStart(lines: string[], index: number) {
  return isTableRow(lines[index] ?? "") && isTableSeparator(lines[index + 1] ?? "");
}

function tableCells(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderMarkdownTable(lines: string[]) {
  const headers = tableCells(lines[0] ?? "");
  const bodyRows = lines.slice(2).map(tableCells);
  const numericColumns = headers.map((_, index) =>
    bodyRows.every((row) => row[index] === "" || Number.isFinite(Number(row[index]))),
  );

  const head = headers
    .map((header, index) => {
      const align = numericColumns[index] ? "text-right" : "text-left";
      return `<th class="whitespace-nowrap px-3 py-2 font-medium ${align}">${inlineMarkdown(
        escapeHtml(header),
      )}</th>`;
    })
    .join("");
  const body = bodyRows
    .map((row) => {
      const cells = headers
        .map((_, index) => {
          const align = numericColumns[index] ? "text-right tabular-nums" : "text-left";
          return `<td class="whitespace-nowrap border-t border-border px-3 py-2 ${align}">${inlineMarkdown(
            escapeHtml(row[index] ?? ""),
          )}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  return `<div class="my-3 max-w-full overflow-x-auto rounded-lg border border-border bg-card/70"><table class="min-w-full border-collapse text-xs"><thead class="bg-muted/70"><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

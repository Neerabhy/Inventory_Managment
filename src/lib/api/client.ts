import { getToken, setToken } from "./token";

export const API_BASE =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** If true, send body as application/x-www-form-urlencoded (for OAuth2 token endpoints). */
  form?: boolean;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: Record<string, string> = { Accept: "application/json", ...opts.headers };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    if (opts.form) {
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      const params = new URLSearchParams();
      Object.entries(opts.body as Record<string, string>).forEach(([k, v]) => params.append(k, String(v)));
      body = params.toString();
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
  }

  const res = await fetch(url, { method: opts.method ?? "GET", headers, body, signal: opts.signal });

  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!res.ok) {
    if (res.status === 401) setToken(null);
    const msg =
      (data && typeof data === "object" && "message" in data && typeof (data as any).message === "string"
        ? (data as any).message
        : data && typeof data === "object" && "detail" in data
          ? typeof (data as any).detail === "string" ? (data as any).detail : JSON.stringify((data as any).detail)
          : `Request failed (${res.status})`);
    throw new ApiError(msg, res.status, data);
  }
  return data as T;
}

// JWT storage — localStorage + in-memory mirror
const KEY = "aic.token";
let memToken: string | null = null;

export function getToken(): string | null {
  if (memToken) return memToken;
  if (typeof window === "undefined") return null;
  memToken = window.localStorage.getItem(KEY);
  return memToken;
}

export function setToken(token: string | null) {
  memToken = token;
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(KEY, token);
  else window.localStorage.removeItem(KEY);
}

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchMe, login as loginApi, logout as logoutApi, type AuthUser } from "./api/auth";
import { getToken } from "./api/token";

interface AuthCtx {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    const t = getToken();
    setTokenState(t);
    if (!t) { setUser(null); return; }
    try { setUser(await fetchMe()); }
    catch { setUser(null); setTokenState(null); }
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);

  const value: AuthCtx = {
    user,
    token,
    loading,
    login: async (username, password) => {
      const res = await loginApi(username, password);
      setTokenState(res.access_token);
      if (res.user) setUser(res.user);
      else await refresh();
    },
    logout: () => {
      logoutApi();
      setUser(null);
      setTokenState(null);
    },
    refresh,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

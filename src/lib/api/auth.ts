import { api } from "./client";
import { setToken } from "./token";

export interface AuthUser {
  user_id?: number;
  username: string;
  full_name?: string;
  email?: string;
  department?: string;
  roles?: string[];
  [key: string]: unknown;
}

interface LoginResponse {
  access_token: string;
  token_type?: string;
  user?: AuthUser;
}

/**
 * POST /api/v1/auth/login — tries JSON first, falls back to form-encoded
 * (FastAPI's OAuth2PasswordRequestForm).
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  try {
    const res = await api<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: { username, password },
    });
    setToken(res.access_token);
    return res;
  } catch (e: any) {
    if (e?.status === 422 || e?.status === 400 || e?.status === 415) {
      const res = await api<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        form: true,
        body: { username, password },
      });
      setToken(res.access_token);
      return res;
    }
    throw e;
  }
}

export async function fetchMe(): Promise<AuthUser> {
  return api<AuthUser>("/api/v1/auth/me");
}

export function logout() {
  setToken(null);
}

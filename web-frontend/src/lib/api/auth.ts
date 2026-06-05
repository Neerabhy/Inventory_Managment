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

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  roles?: string[];
}

/**
 * POST /api/v1/auth/login — tries JSON first, falls back to form-encoded
 * (FastAPI's OAuth2PasswordRequestForm).
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const loginId = username.trim();
  try {
    const res = await api<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: { username: loginId, password },
    });
    setToken(res.access_token);
    return res;
  } catch (e: unknown) {
    const status =
      typeof e === "object" && e !== null && "status" in e
        ? (e as { status?: number }).status
        : undefined;
    if (status === 422 || status === 400 || status === 415) {
      const res = await api<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        form: true,
        body: { username: loginId, password },
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

export async function register(payload: RegisterPayload): Promise<AuthUser> {
  return api<AuthUser>("/api/v1/auth/signup", {
    method: "POST",
    body: {
      ...payload,
      roles: payload.roles?.length ? payload.roles : ["PROCUREMENT_MGR"],
    },
  });
}

export function logout() {
  setToken(null);
}

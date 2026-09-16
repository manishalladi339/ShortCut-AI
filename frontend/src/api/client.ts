/** Minimal API client. Bearer token attached when present. */
import { storage } from "@/src/utils/storage";

const BASE = `${(process.env.EXPO_PUBLIC_BACKEND_URL ?? "").replace(/\/$/, "")}/api/v1`;

export const TOKEN_KEY = "shortcut.access_token";
export const REFRESH_KEY = "shortcut.refresh_token";

export type ApiError = { code: string; message: string };

async function getToken(): Promise<string | null> {
  return await storage.secureGet(TOKEN_KEY, null as string | null);
}

export async function setTokens(access: string, refresh: string): Promise<void> {
  await storage.secureSet(TOKEN_KEY, access);
  await storage.secureSet(REFRESH_KEY, refresh);
}

export async function clearTokens(): Promise<void> {
  await storage.secureRemove(TOKEN_KEY);
  await storage.secureRemove(REFRESH_KEY);
}

let refreshing: Promise<boolean> | null = null;
async function refreshOnce(): Promise<boolean> {
  if (!refreshing) refreshing = performRefresh().finally(() => { refreshing = null; });
  return refreshing;
}

async function performRefresh(): Promise<boolean> {
  const refresh = await storage.secureGet(REFRESH_KEY, null as string | null);
  if (!refresh) return false;
  try {
    const r = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!r.ok) return false;
    const data = await r.json();
    await setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function api<T>(
  path: string,
  opts: { method?: string; body?: any; auth?: boolean; raw?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true, raw = false } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = await getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const init: RequestInit = {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  };
  let r = await fetch(`${BASE}${path}`, init);

  if (r.status === 401 && auth) {
    const ok = await refreshOnce();
    if (ok) {
      const token = await getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
      r = await fetch(`${BASE}${path}`, { ...init, headers });
    }
  }

  if (raw) return (await r.text()) as unknown as T;

  const text = await r.text();
  let data: any = {};
  try { data = text ? JSON.parse(text) : {}; } catch {
    throw { code: "invalid_response", message: "The server returned an unreadable response. Please try again." };
  }
  if (!r.ok) {
    const err: ApiError = data?.error ?? { code: "http_error", message: Array.isArray(data?.detail) ? data.detail.map((d: any) => d.msg).join("; ") : (data?.detail ?? r.statusText) };
    throw err;
  }
  return data as T;
}

export const apiBase = BASE;

import { clearAuthTokens, getAccessToken, getRefreshToken, setAccessToken } from "@/lib/auth";

// Empty string = relative URL so browser calls /api/v1/... on the same host.
// Next.js rewrites proxy /api/* → Django internally (see next.config.js).
const BASE = "";

class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });

  if (res.status === 401) {
    // Attempt token refresh
    const refreshed = await refreshTokens();
    if (refreshed) {
      const refreshedToken = getAccessToken();
      if (refreshedToken) headers["Authorization"] = `Bearer ${refreshedToken}`;
      const retry = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });
      if (!retry.ok) throw new ApiError(retry.status, "Unauthorized");
      return retry.json();
    }
    clearAuthTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, res.statusText, data);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function refreshTokens(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${BASE}/api/v1/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setAccessToken(data.access);
    return true;
  } catch {
    return false;
  }
}

export const refreshAccessToken = refreshTokens;

// api can be called directly as api(path, init?) for GET, or via api.get/post/patch/put/delete
function apiFn<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init);
}
apiFn.get    = <T>(path: string) => request<T>(path);
apiFn.post   = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
apiFn.patch  = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
apiFn.put    = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });
apiFn.delete = <T>(path: string) => request<T>(path, { method: "DELETE" });

export const api = apiFn;

export { ApiError };

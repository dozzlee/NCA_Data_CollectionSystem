import Cookies from "js-cookie";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = Cookies.get("access_token");
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
      headers["Authorization"] = `Bearer ${Cookies.get("access_token")}`;
      const retry = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });
      if (!retry.ok) throw new ApiError(retry.status, "Unauthorized");
      return retry.json();
    }
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    window.location.href = "/login";
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
  const refresh = Cookies.get("refresh_token");
  if (!refresh) return false;
  try {
    const res = await fetch(`${BASE}/api/v1/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    Cookies.set("access_token", data.access, { expires: 1 / 96 }); // 15 min
    return true;
  } catch {
    return false;
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { ApiError };

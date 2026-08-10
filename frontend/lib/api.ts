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
  const res = await authenticatedFetch(path, init);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, detail, data);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });

  if (res.status === 401) {
    // Attempt token refresh
    const refreshed = await refreshTokens();
    if (refreshed) {
      const refreshedToken = getAccessToken();
      if (refreshedToken) headers.set("Authorization", `Bearer ${refreshedToken}`);
      res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });
      return res;
    }
    clearAuthTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Session expired");
  }
  return res;
}

export async function downloadAuthenticated(
  path: string,
  init: RequestInit,
  fallbackFilename: string
): Promise<string> {
  const res = await authenticatedFetch(path, init);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = typeof data?.detail === "string" ? data.detail : "Download failed.";
    throw new ApiError(res.status, detail, data);
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("text/csv") && !contentType.includes("application/octet-stream")
      && !contentType.includes("application/pdf")
      && !contentType.includes("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) {
    throw new ApiError(res.status, "The server returned an unexpected download format.");
  }

  const disposition = res.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quoted = disposition.match(/filename="([^"]+)"/i)?.[1];
  const filename = encoded ? decodeURIComponent(encoded) : quoted ?? fallbackFilename;
  const url = URL.createObjectURL(await res.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  window.setTimeout(() => {
    anchor.remove();
    URL.revokeObjectURL(url);
  }, 1000);
  return filename;
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
apiFn.upload = <T>(path: string, form: FormData) =>
  request<T>(path, { method: "POST", body: form });

export const api = apiFn;

export { ApiError };

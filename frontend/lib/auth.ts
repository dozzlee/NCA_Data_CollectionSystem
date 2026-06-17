import Cookies from "js-cookie";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

const accessCookieOptions = {
  expires: 1 / 96, // 15 minutes
  sameSite: "lax" as const,
  path: "/",
};

const refreshCookieOptions = {
  expires: 7,
  sameSite: "lax" as const,
  path: "/",
};

function readLocalStorage(key: string): string | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    return window.localStorage.getItem(key) ?? undefined;
  } catch {
    return undefined;
  }
}

function writeLocalStorage(key: string, value: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Cookie storage remains the fallback when localStorage is unavailable.
  }
}

function removeLocalStorage(key: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Best-effort cleanup.
  }
}

export function getAccessToken(): string | undefined {
  return readLocalStorage(ACCESS_TOKEN_KEY) ?? Cookies.get(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | undefined {
  return readLocalStorage(REFRESH_TOKEN_KEY) ?? Cookies.get(REFRESH_TOKEN_KEY);
}

export function setAccessToken(access: string) {
  Cookies.set(ACCESS_TOKEN_KEY, access, accessCookieOptions);
  writeLocalStorage(ACCESS_TOKEN_KEY, access);
}

export function setAuthTokens(tokens: { access: string; refresh: string }) {
  setAccessToken(tokens.access);
  Cookies.set(REFRESH_TOKEN_KEY, tokens.refresh, refreshCookieOptions);
  writeLocalStorage(REFRESH_TOKEN_KEY, tokens.refresh);
}

export function clearAuthTokens() {
  Cookies.remove(ACCESS_TOKEN_KEY);
  Cookies.remove(ACCESS_TOKEN_KEY, { path: "/" });
  Cookies.remove(REFRESH_TOKEN_KEY);
  Cookies.remove(REFRESH_TOKEN_KEY, { path: "/" });
  removeLocalStorage(ACCESS_TOKEN_KEY);
  removeLocalStorage(REFRESH_TOKEN_KEY);
}

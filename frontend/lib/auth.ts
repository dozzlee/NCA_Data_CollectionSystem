/** Authentication tokens are server-issued HttpOnly cookies and never exposed to JavaScript. */
export function clearAuthTokens() {
  if (typeof window === "undefined") return;
  // Remove obsolete tokens left by pre-remediation releases.
  window.localStorage.removeItem("access_token");
  window.localStorage.removeItem("refresh_token");
}

export function getAccessToken(): undefined { return undefined; }
export function getRefreshToken(): undefined { return undefined; }
export function setAccessToken(): void { /* HttpOnly cookie is set by the backend. */ }
export function setAuthTokens(): void { clearAuthTokens(); }

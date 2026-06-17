"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clearAuthTokens, getAccessToken } from "@/lib/auth";

const WARNING_BEFORE_MS = 2 * 60 * 1000; // warn 2 min before expiry

function getTokenExpiry(): number | null {
  if (typeof window === "undefined") return null;
  const token = getAccessToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function useSessionTimeout(onRefresh: () => Promise<boolean>) {
  const [showWarning, setShowWarning] = useState(false);
  const router = useRouter();
  const warningTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearTimers() {
    if (warningTimer.current) clearTimeout(warningTimer.current);
    if (logoutTimer.current) clearTimeout(logoutTimer.current);
  }

  function scheduleTimers() {
    clearTimers();
    const expiry = getTokenExpiry();
    if (!expiry) return;
    const now = Date.now();
    const msUntilExpiry = expiry - now;
    if (msUntilExpiry <= 0) {
      logout();
      return;
    }
    const msUntilWarning = msUntilExpiry - WARNING_BEFORE_MS;
    if (msUntilWarning > 0) {
      warningTimer.current = setTimeout(() => setShowWarning(true), msUntilWarning);
    } else {
      setShowWarning(true);
    }
    logoutTimer.current = setTimeout(logout, msUntilExpiry);
  }

  function logout() {
    clearTimers();
    clearAuthTokens();
    router.push("/login");
  }

  async function handleStaySignedIn() {
    const ok = await onRefresh();
    if (ok) {
      setShowWarning(false);
      scheduleTimers();
    } else {
      logout();
    }
  }

  useEffect(() => {
    scheduleTimers();
    return clearTimers;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { showWarning, handleStaySignedIn, handleSignOut: logout };
}

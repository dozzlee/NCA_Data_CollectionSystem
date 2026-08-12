"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const WARNING_BEFORE_MS = 2 * 60 * 1000;

export function useSessionTimeout(onRefresh: () => Promise<boolean>) {
  const [showWarning, setShowWarning] = useState(false);
  const router = useRouter();
  const warningTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    if (warningTimer.current) clearTimeout(warningTimer.current);
    if (logoutTimer.current) clearTimeout(logoutTimer.current);
  }, []);

  const logout = useCallback(async () => {
    clearTimers();
    try { await api.post("/auth/logout/"); } catch { /* Session may already be expired. */ }
    router.push("/login");
  }, [clearTimers, router]);

  const scheduleTimers = useCallback(() => {
    clearTimers(); setShowWarning(false);
    warningTimer.current = setTimeout(() => setShowWarning(true), IDLE_TIMEOUT_MS - WARNING_BEFORE_MS);
    logoutTimer.current = setTimeout(logout, IDLE_TIMEOUT_MS);
  }, [clearTimers, logout]);

  async function handleStaySignedIn() {
    const ok = await onRefresh();
    if (ok) scheduleTimers(); else await logout();
  }

  useEffect(() => {
    const activity = () => scheduleTimers();
    const events = ["mousedown", "keydown", "touchstart", "scroll"] as const;
    events.forEach((event) => window.addEventListener(event, activity, { passive: true }));
    scheduleTimers();
    return () => { clearTimers(); events.forEach((event) => window.removeEventListener(event, activity)); };
  }, [clearTimers, scheduleTimers]);

  return { showWarning, handleStaySignedIn, handleSignOut: logout };
}

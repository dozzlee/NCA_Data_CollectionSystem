"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Search, AlertTriangle, Clock, CheckCircle2, MessageSquare } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ReportingPeriod } from "@/lib/types";

interface DashboardSummary {
  overdue: number;
  correction_requested: number;
  submitted: number;
  under_review: number;
  pending_approval: number;
  due_soon: number;
}

interface NotificationItem {
  id: string;
  icon: React.ReactNode;
  color: string;
  bg: string;
  label: string;
  count: number;
  href: string;
}

function NotificationPanel({ onClose }: { onClose: () => void }) {
  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary-notif"],
    queryFn: () => api("/dashboard/summary/"),
    staleTime: 30 * 1000,
  });

  const { data: periodsData } = useQuery<{ results: ReportingPeriod[] }>({
    queryKey: ["active-periods-notif"],
    queryFn: () => api("/periods/?status=ACTIVE&ordering=-year"),
    staleTime: 60 * 1000,
  });

  const activePeriods = periodsData?.results ?? [];

  const notifications: NotificationItem[] = [
    {
      id: "overdue",
      icon: <AlertTriangle size={14} />,
      color: "#c0112a",
      bg: "#ffe8e8",
      label: "Overdue submissions",
      count: summary?.overdue ?? 0,
      href: "/submissions?due_state=OVERDUE",
    },
    {
      id: "correction",
      icon: <MessageSquare size={14} />,
      color: "#c0112a",
      bg: "#ffe8e8",
      label: "Correction requested",
      count: summary?.correction_requested ?? 0,
      href: "/submissions?workflow_status=CORRECTION_REQUESTED",
    },
    {
      id: "pending_approval",
      icon: <Clock size={14} />,
      color: "#7a5c00",
      bg: "#fff3bf",
      label: "Pending provider approval",
      count: summary?.pending_approval ?? 0,
      href: "/submissions?workflow_status=PENDING_APPROVAL",
    },
    {
      id: "review",
      icon: <Clock size={14} />,
      color: "#004999",
      bg: "#e8f1fb",
      label: "Awaiting NCA review",
      count: (summary?.submitted ?? 0) + (summary?.under_review ?? 0),
      href: "/submissions?workflow_status=SUBMITTED",
    },
    {
      id: "due_soon",
      icon: <Clock size={14} />,
      color: "#7a5c00",
      bg: "#fff3bf",
      label: "Due within 7 days",
      count: summary?.due_soon ?? 0,
      href: "/submissions?due_state=DUE_SOON",
    },
  ].filter(n => n.count > 0);

  const totalAlerts = (summary?.overdue ?? 0) + (summary?.correction_requested ?? 0);

  return (
    <div className="absolute right-0 top-full mt-2 z-50 w-[340px] rounded-[16px] border border-[#eceef0] bg-white shadow-[0_16px_42px_rgba(0,45,91,0.14)] overflow-hidden">
      {/* Header */}
      <div className="border-b border-[#eceef0] px-5 py-3.5 flex items-center justify-between">
        <span className="text-[14px] font-semibold text-[#191c1e]">Notifications</span>
        {totalAlerts > 0 && (
          <span className="rounded-full bg-[#e31937] px-2 py-0.5 text-[11px] font-bold text-white">
            {totalAlerts} urgent
          </span>
        )}
      </div>

      {/* Alerts */}
      {notifications.length === 0 ? (
        <div className="px-5 py-8 text-center">
          <CheckCircle2 size={24} className="mx-auto text-[#1f7a4d] mb-2" />
          <p className="text-[13px] font-medium text-[#191c1e]">All clear</p>
          <p className="text-[12px] text-[#737780] mt-0.5">No urgent items need your attention.</p>
        </div>
      ) : (
        <div className="divide-y divide-[#eceef0]">
          {notifications.map(n => (
            <Link key={n.id} href={n.href} onClick={onClose}
              className="flex items-center gap-3 px-5 py-3 hover:bg-[#f7f9fb] transition-colors">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
                style={{ background: n.bg, color: n.color }}>
                {n.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-[#191c1e]">{n.label}</p>
              </div>
              <span className="shrink-0 rounded-full px-2.5 py-0.5 text-[12px] font-bold"
                style={{ background: n.bg, color: n.color }}>
                {n.count}
              </span>
            </Link>
          ))}
        </div>
      )}

      {/* Active periods */}
      {activePeriods.length > 0 && (
        <>
          <div className="border-t border-[#eceef0] px-5 py-2.5 bg-[#f7f9fb]">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[#737780]">Active Periods</p>
          </div>
          <div className="divide-y divide-[#eceef0]">
            {activePeriods.slice(0, 3).map(p => (
              <Link key={p.id} href={`/periods/${p.id}`} onClick={onClose}
                className="flex items-center justify-between px-5 py-2.5 hover:bg-[#f7f9fb] transition-colors">
                <div>
                  <p className="text-[12px] font-medium text-[#191c1e]">{p.name}</p>
                  <p className="text-[11px] text-[#737780]">
                    Due {new Date(p.due_at).toLocaleDateString("en-GB", { day:"numeric", month:"short" })}
                  </p>
                </div>
                <span className="text-[10px] font-semibold uppercase tracking-wide text-[#1f7a4d] bg-[#e5f4eb] rounded-full px-2 py-0.5">
                  Active
                </span>
              </Link>
            ))}
          </div>
        </>
      )}

      {/* Footer */}
      <div className="border-t border-[#eceef0] px-5 py-3">
        <Link href="/submissions" onClick={onClose}
          className="text-[12px] font-medium text-[#0066cc] hover:underline">
          View all submissions →
        </Link>
      </div>
    </div>
  );
}

export function TopBar() {
  const [notifOpen, setNotifOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Count urgent items for the badge
  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary-notif"],
    queryFn: () => api("/dashboard/summary/"),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000, // refresh every minute
  });

  const urgentCount = (summary?.overdue ?? 0) + (summary?.correction_requested ?? 0);

  // Active period for indicator
  const { data: periodsData } = useQuery<{ results: ReportingPeriod[] }>({
    queryKey: ["active-periods-notif"],
    queryFn: () => api("/periods/?status=ACTIVE&ordering=-year"),
    staleTime: 60 * 1000,
  });
  const latestActive = periodsData?.results?.[0];

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-[#e6e8ea] bg-white px-6">
      {/* Search */}
      <div className="flex flex-1 max-w-sm items-center gap-2 rounded-[8px] border border-[#c3c6d0] bg-[#f7f9fb] px-3 py-1.5 text-[13px] text-[#43474f]">
        <Search size={13} className="shrink-0 text-[#737780]" />
        <input
          type="search"
          placeholder="Search providers, submissions…"
          className="flex-1 bg-transparent outline-none placeholder:text-[#737780] text-[13px]"
        />
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* Notification bell */}
        <div ref={ref} className="relative">
          <button
            onClick={() => setNotifOpen(v => !v)}
            className="relative flex h-8 w-8 items-center justify-center rounded-[8px] text-[#43474f] hover:bg-[#eceef0] transition-colors"
            aria-label="Notifications"
          >
            <Bell size={16} />
            {urgentCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#E31937] px-1 text-[9px] font-bold text-white leading-none">
                {urgentCount > 9 ? "9+" : urgentCount}
              </span>
            )}
          </button>
          {notifOpen && <NotificationPanel onClose={() => setNotifOpen(false)} />}
        </div>

        {/* Active period indicator */}
        {latestActive && (
          <Link href={`/periods/${latestActive.id}`}
            className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] px-3 py-1.5 hover:bg-[#f7f9fb] transition-colors">
            <span className="h-2 w-2 rounded-full bg-[#1f7a4d]" />
            <span className="text-[12px] font-medium text-[#191c1e] max-w-[140px] truncate">{latestActive.name}</span>
            <span className="text-[11px] text-[#737780]">Active</span>
          </Link>
        )}
      </div>
    </header>
  );
}

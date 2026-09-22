"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, AlertTriangle, Clock, CheckCircle2, MessageSquare } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ReportingPeriod, User } from "@/lib/types";

interface RequestNotification {
  id: number;
  request: string;
  request_title: string;
  title: string;
  message: string;
  created_at: string;
  read_at: string | null;
}

interface RequestNotificationResponse {
  unread_count: number;
  results: RequestNotification[];
}

interface SubmissionNotificationResponse {
  results: { id:number; submission:number; title:string; message:string; is_read:boolean; created_at:string; form_code:string; provider_name:string }[];
}

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

function NotificationPanel({ onClose, isRequester }: { onClose: () => void; isRequester: boolean }) {
  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary-notif"],
    queryFn: () => api("/dashboard/summary/"),
    staleTime: 30 * 1000,
    enabled: !isRequester,
  });

  const { data: periodsData } = useQuery<{ results: ReportingPeriod[] }>({
    queryKey: ["active-periods-notif"],
    queryFn: () => api("/periods/?status=ACTIVE&ordering=-year"),
    staleTime: 60 * 1000,
    enabled: !isRequester,
  });

  const { data: requestNotifications } = useQuery<RequestNotificationResponse>({
    queryKey: ["data-request-notifications"],
    queryFn: () => api("/data-request-notifications/"),
    staleTime: 30 * 1000,
    enabled: true,
  });
  const { data: submissionNotifications } = useQuery<SubmissionNotificationResponse>({
    queryKey: ["submission-notifications"],
    queryFn: () => api("/submission-notifications/"),
    staleTime: 30 * 1000,
    enabled: !isRequester,
  });

  if (isRequester) {
    const items = requestNotifications?.results ?? [];
    return (
      <div className="absolute right-0 top-full mt-2 z-50 w-[360px] rounded-[16px] border border-[#eceef0] bg-white shadow-[0_16px_42px_rgba(0,45,91,0.14)] overflow-hidden">
        <div className="border-b border-[#eceef0] px-5 py-3.5 flex items-center justify-between">
          <span className="text-[14px] font-semibold text-[#191c1e]">Request notifications</span>
          {(requestNotifications?.unread_count ?? 0) > 0 && (
            <span className="rounded-full bg-[#0066cc] px-2 py-0.5 text-[11px] font-bold text-white">
              {requestNotifications?.unread_count} new
            </span>
          )}
        </div>
        {items.length === 0 ? (
          <p className="px-5 py-8 text-center text-[12px] text-[#737780]">No request updates yet.</p>
        ) : (
          <div className="divide-y divide-[#eceef0] max-h-[360px] overflow-y-auto">
            {items.slice(0, 8).map(item => (
              <Link key={item.id} href={`/data-requests?id=${item.request}`} onClick={onClose}
                className={`block px-5 py-3 hover:bg-[#f7f9fb] ${item.read_at ? "" : "bg-[#f4f8fd]"}`}>
                <p className="text-[12px] font-semibold text-[#191c1e]">{item.title}</p>
                <p className="text-[11px] text-[#43474f] mt-0.5 line-clamp-2">{item.message}</p>
                <p className="text-[10px] text-[#737780] mt-1">{item.request_title}</p>
              </Link>
            ))}
          </div>
        )}
        <div className="border-t border-[#eceef0] px-5 py-3">
          <Link href="/notifications" onClick={onClose} className="text-[12px] font-medium text-[#0066cc] hover:underline">
            View all notifications →
          </Link>
        </div>
      </div>
    );
  }

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
      label: "Flag requested",
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

  const workflowNotices = submissionNotifications?.results ?? [];
  const dataRequestNotices = requestNotifications?.results ?? [];

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
      {dataRequestNotices.length > 0 && (
        <div className="max-h-[180px] divide-y divide-[#eceef0] overflow-y-auto border-b border-[#eceef0]">
          {dataRequestNotices.slice(0, 5).map(item => (
            <Link key={`request-${item.id}`} href={`/data-requests?id=${item.request}`} onClick={onClose}
              className={`block px-5 py-3 hover:bg-[#f7f9fb] ${item.read_at ? "" : "bg-[#f4f8fd]"}`}>
              <p className="text-[12px] font-semibold text-[#191c1e]">{item.title}</p>
              <p className="mt-0.5 line-clamp-2 text-[11px] text-[#43474f]">{item.message}</p>
              <p className="mt-1 text-[10px] text-[#737780]">Data request · {item.request_title}</p>
            </Link>
          ))}
        </div>
      )}
      {workflowNotices.length > 0 && (
        <div className="max-h-[220px] divide-y divide-[#eceef0] overflow-y-auto">
          {workflowNotices.slice(0, 6).map(item => (
            <Link key={item.id} href={`/submissions/${item.submission}/review`} onClick={onClose}
              className={`block px-5 py-3 hover:bg-[#f7f9fb] ${item.is_read ? "" : "bg-[#f4f8fd]"}`}>
              <p className="text-[12px] font-semibold text-[#191c1e]">{item.title}</p>
              <p className="mt-0.5 line-clamp-2 text-[11px] text-[#43474f]">{item.message}</p>
              <p className="mt-1 text-[10px] text-[#737780]">{item.form_code} · {item.provider_name}</p>
            </Link>
          ))}
        </div>
      )}
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
  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => api("/auth/me/"),
    staleTime: 5 * 60 * 1000,
  });
  const isRequester = user?.role === "NCA_VIEWER";

  // Count urgent items for the badge
  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary-notif"],
    queryFn: () => api("/dashboard/summary/"),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000, // refresh every minute
    enabled: user !== undefined && !isRequester,
  });

  const { data: requestNotifications } = useQuery<RequestNotificationResponse>({
    queryKey: ["data-request-notifications"],
    queryFn: () => api("/data-request-notifications/"),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
    enabled: user !== undefined,
  });
  const { data: submissionNotifications } = useQuery<SubmissionNotificationResponse>({
    queryKey: ["submission-notifications"],
    queryFn: () => api("/submission-notifications/?unread=true"),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
    enabled: user !== undefined && !isRequester,
  });

  const urgentCount = isRequester
    ? requestNotifications?.unread_count ?? 0
    : (summary?.overdue ?? 0) + (summary?.correction_requested ?? 0)
      + (submissionNotifications?.results.filter(item => !item.is_read).length ?? 0)
      + (requestNotifications?.unread_count ?? 0);

  // Active period for indicator
  const { data: periodsData } = useQuery<{ results: ReportingPeriod[] }>({
    queryKey: ["active-periods-notif"],
    queryFn: () => api("/periods/?status=ACTIVE&ordering=-year"),
    staleTime: 60 * 1000,
    enabled: user !== undefined && !isRequester,
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
    <header className="workspace-header relative z-30 flex h-14 shrink-0 items-center gap-4 border-b px-6">
      <div className="flex flex-1 items-center justify-end gap-2">
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
          {notifOpen && <NotificationPanel onClose={() => setNotifOpen(false)} isRequester={isRequester} />}
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

"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { BarChart3, LayoutDashboard, Clock, CheckCircle, HelpCircle, LogOut, ShieldAlert, Bell } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SubmissionNotificationSummary, User } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  PROVIDER_DATA_ENTRY: "Data Entry",
  PROVIDER_APPROVER:   "Approver",
  PROVIDER_ADMIN:      "Admin",
};

const DATA_ENTRY_NAV = [
  { href: "/provider/dashboard",    label: "My Forms",    icon: LayoutDashboard },
  { href: "/industry-dashboard",    label: "Industry",    icon: BarChart3 },
  { href: "/provider/history",      label: "History",     icon: Clock },
  { href: "/provider/compliance",   label: "Corrections", icon: ShieldAlert },
  { href: "/provider/inquiries",    label: "Technical Support",   icon: HelpCircle },
  { href: "/provider/notifications",label: "Updates",      icon: Bell },
];

const APPROVER_NAV = [
  { href: "/provider/dashboard",         label: "My Forms",         icon: LayoutDashboard },
  { href: "/industry-dashboard",         label: "Industry",         icon: BarChart3 },
  { href: "/provider/pending-approval",  label: "Pending Approval", icon: CheckCircle },
  { href: "/provider/history",           label: "History",          icon: Clock },
  { href: "/provider/compliance",        label: "Compliance",       icon: ShieldAlert },
  { href: "/provider/inquiries",         label: "Inquiries",        icon: HelpCircle },
  { href: "/provider/notifications",     label: "Updates",          icon: Bell },
];

export function ProviderTopBar() {
  const pathname = usePathname();
  const router = useRouter();

  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => api("/auth/me/"),
    staleTime: 5 * 60 * 1000,
  });

  async function handleSignOut() {
    try { await api.post("/auth/logout/"); } catch { /* Always leave the local session. */ }
    router.push("/login");
  }

  const isApprover = user?.role === "PROVIDER_APPROVER";
  const nav = isApprover ? APPROVER_NAV : DATA_ENTRY_NAV;
  const { data: notificationSummary } = useQuery<SubmissionNotificationSummary>({
    queryKey: ["submission-notification-summary"],
    queryFn: () => api("/submission-notifications/summary/"),
    enabled: Boolean(user?.role?.startsWith("PROVIDER_")),
    refetchInterval: 30_000,
  });

  return (
    <header className="sticky top-0 z-40 border-b border-[#e6e8ea] bg-white">
      <div className="mx-auto flex min-h-14 max-w-[1200px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6">
        {/* Brand */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-[#e6e8ea]">
            <Image src="/nca-logo.png" alt="National Communications Authority" width={32} height={32} className="h-full w-full object-contain" />
          </div>
          <span className="text-[13px] font-semibold text-[#191c1e]">Data Collection</span>
        </div>

        <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto pb-1 lg:order-none lg:w-auto lg:pb-0">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link key={href} href={href}
                className={cn(
                  "flex items-center gap-2 rounded-[8px] px-3 py-1.5 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-[#eceef0] text-[#191c1e]"
                    : "text-[#43474f] hover:bg-[#f2f4f6] hover:text-[#191c1e]"
                )}>
                <Icon size={14} />
                {label}
                {href === "/provider/notifications" && Boolean(notificationSummary?.unread) && <span className="rounded-full bg-[#e31937] px-1.5 text-[10px] text-white">{notificationSummary!.unread}</span>}
                {href === "/provider/pending-approval" && Boolean(notificationSummary?.pending_approval) && <span className="rounded-full bg-[#ffd100] px-1.5 text-[10px] text-[#191c1e]">{notificationSummary!.pending_approval}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {user && (
            <div className="text-right">
              <p className="text-[12px] font-medium text-[#191c1e]">{user.name}</p>
              <p className="text-[11px] text-[#737780]">
                {user.organization?.name} · {ROLE_LABELS[user.role] ?? user.role}
              </p>
            </div>
          )}
          <button onClick={handleSignOut}
            className="flex items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12px] text-[#737780] hover:bg-[#eceef0] hover:text-[#191c1e] transition-colors">
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

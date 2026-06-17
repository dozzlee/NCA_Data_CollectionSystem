"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Clock, CheckCircle, HelpCircle, LogOut, ShieldAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { clearAuthTokens } from "@/lib/auth";
import type { User } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  PROVIDER_DATA_ENTRY: "Data Entry",
  PROVIDER_APPROVER:   "Approver",
  PROVIDER_ADMIN:      "Admin",
};

const DATA_ENTRY_NAV = [
  { href: "/provider/dashboard",    label: "My Forms",    icon: LayoutDashboard },
  { href: "/provider/history",      label: "History",     icon: Clock },
  { href: "/provider/compliance",   label: "Compliance",  icon: ShieldAlert },
  { href: "/provider/inquiries",    label: "Inquiries",   icon: HelpCircle },
];

const APPROVER_NAV = [
  { href: "/provider/dashboard",         label: "My Forms",         icon: LayoutDashboard },
  { href: "/provider/pending-approval",  label: "Pending Approval", icon: CheckCircle },
  { href: "/provider/history",           label: "History",          icon: Clock },
  { href: "/provider/compliance",        label: "Compliance",       icon: ShieldAlert },
  { href: "/provider/inquiries",         label: "Inquiries",        icon: HelpCircle },
];

export function ProviderTopBar() {
  const pathname = usePathname();
  const router = useRouter();

  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => api("/auth/me/"),
    staleTime: 5 * 60 * 1000,
  });

  function handleSignOut() {
    clearAuthTokens();
    router.push("/login");
  }

  const isApprover = user?.role === "PROVIDER_APPROVER";
  const nav = isApprover ? APPROVER_NAV : DATA_ENTRY_NAV;

  return (
    <header className="sticky top-0 z-40 border-b border-[#e6e8ea] bg-white">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-6 px-6">
        {/* Brand */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-[#E31937] text-[9px] font-bold text-white tracking-wider">
            NCA
          </div>
          <span className="text-[13px] font-semibold text-[#191c1e]">Data Collection</span>
        </div>

        <nav className="flex items-center gap-1">
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

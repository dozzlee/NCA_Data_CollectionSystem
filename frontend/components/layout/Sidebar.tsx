"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, BarChart3, FileText, Building2, Calendar,
  ShieldAlert, Download, LogOut, FormInput, Users,
  Library, ClipboardList, Bell,
  ShieldCheck, LifeBuoy,
} from "lucide-react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  NCA_ADMIN:   "System Administrator",
  NCA_OFFICER: "NCA Officer",
  NCA_VIEWER:  "NCA Data Requester",
};

// Base nav — shown to all NCA roles
const BASE_NAV = [
  { href: "/dashboard",   label: "Dashboard",   icon: LayoutDashboard },
  { href: "/industry-dashboard", label: "Industry Dashboard", icon: BarChart3 },
  { href: "/submissions", label: "Submissions",  icon: FileText },
  { href: "/providers",   label: "Providers",    icon: Building2 },
  { href: "/periods",     label: "Periods",      icon: Calendar },
  { href: "/compliance",  label: "Compliance",   icon: ShieldAlert },
  { href: "/exports",     label: "Exports",      icon: Download },
];

// System Admin only
const ADMIN_NAV = [
  { href: "/forms",  label: "Form Builder", icon: FormInput },
  { href: "/users",  label: "Users",        icon: Users },
  { href: "/data-requests", label: "Data Requests", icon: ClipboardList },
  { href: "/governance", label: "Production Readiness", icon: ShieldCheck },
  { href: "/support", label: "Support Queue", icon: LifeBuoy },
];

const OFFICER_NAV = [
  { href: "/forms",  label: "Form Builder", icon: FormInput },
  { href: "/governance", label: "Production Readiness", icon: ShieldCheck },
  { href: "/support", label: "Support Queue", icon: LifeBuoy },
];

const REQUESTER_NAV = [
  { href: "/industry-dashboard", label: "Industry Dashboard", icon: BarChart3 },
  { href: "/data-catalog", label: "Data Catalog", icon: Library },
  { href: "/data-requests", label: "My Requests", icon: ClipboardList },
  { href: "/notifications", label: "Notifications", icon: Bell },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => api("/auth/me/"),
    staleTime: 5 * 60 * 1000,
  });

  const isAdmin = user?.role === "NCA_ADMIN";
  const isOfficer = user?.role === "NCA_OFFICER";
  const isRequester = user?.role === "NCA_VIEWER";
  const navItems = isRequester ? REQUESTER_NAV : isAdmin ? [...BASE_NAV, ...ADMIN_NAV] : isOfficer ? [...BASE_NAV, ...OFFICER_NAV] : BASE_NAV;

  async function handleSignOut() {
    try { await api.post("/auth/logout/"); } catch { /* Always leave the local session. */ }
    router.push("/login");
  }

  const initials = user?.name
    ? user.name.split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase()
    : "?";

  return (
    <aside
      className="flex h-screen w-[272px] shrink-0 flex-col"
      style={{ background: "linear-gradient(180deg, #002d5b 0%, #001836 100%)" }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-6 py-6 border-b border-white/10">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white">
          <Image src="/nca-logo.png" alt="National Communications Authority" width={44} height={44} className="h-full w-full object-contain" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/50 leading-none mb-0.5">
            National Communications Authority
          </p>
          <p className="text-[13px] font-semibold text-white leading-tight truncate">
            Data Collection System
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-white/35">
          Navigation
        </p>
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link key={href} href={href}
              className={cn(
                "group flex items-center gap-3 rounded-[8px] px-3 py-2.5 text-[14px] font-medium transition-colors duration-150",
                active ? "bg-white/12 text-white" : "text-white/60 hover:bg-white/08 hover:text-white/90"
              )}>
              <Icon size={16} className={cn("shrink-0 transition-colors", active ? "text-white" : "text-white/50 group-hover:text-white/80")} />
              {label}
              {href === "/compliance" && (
                <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#E31937] px-1.5 text-[10px] font-bold text-white leading-none">!</span>
              )}
            </Link>
          );
        })}

        {/* Admin section divider */}
        {(isAdmin || isOfficer) && !isRequester && (
          <p className="px-3 mt-4 mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-white/35">
            Administration
          </p>
        )}
      </nav>

      {/* Footer — real user info */}
      <div className="border-t border-white/10 px-3 py-4">
        <div className="flex items-center gap-3 rounded-[8px] px-3 py-2.5 mb-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs font-semibold text-white uppercase">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium text-white truncate">{user?.name ?? "Loading…"}</p>
            <p className="text-[11px] text-white/45 truncate">{ROLE_LABELS[user?.role ?? ""] ?? user?.role}</p>
          </div>
        </div>
        <button onClick={handleSignOut}
          className="flex w-full items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] text-white/50 hover:text-white/80 hover:bg-white/08 transition-colors">
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  );
}

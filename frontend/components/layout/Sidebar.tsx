"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  Building2,
  Calendar,
  ShieldAlert,
  Download,
  LogOut,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/submissions", label: "Submissions", icon: FileText },
  { href: "/providers", label: "Providers", icon: Building2 },
  { href: "/periods", label: "Periods", icon: Calendar },
  { href: "/compliance", label: "Compliance", icon: ShieldAlert },
  { href: "/exports", label: "Exports", icon: Download },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="flex h-screen w-[272px] shrink-0 flex-col"
      style={{
        background: "linear-gradient(180deg, #002d5b 0%, #001836 100%)",
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-6 py-6 border-b border-white/10">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] text-xs font-bold tracking-wider text-white"
          style={{ background: "#E31937" }}
        >
          NCA
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
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group flex items-center gap-3 rounded-[8px] px-3 py-2.5 text-[14px] font-medium transition-colors duration-150",
                active
                  ? "bg-white/12 text-white"
                  : "text-white/60 hover:bg-white/08 hover:text-white/90"
              )}
            >
              <Icon
                size={16}
                className={cn(
                  "shrink-0 transition-colors",
                  active ? "text-white" : "text-white/50 group-hover:text-white/80"
                )}
              />
              {label}
              {href === "/compliance" && (
                <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#E31937] px-1.5 text-[10px] font-bold text-white leading-none">
                  !
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/10 px-3 py-4">
        <div className="flex items-center gap-3 rounded-[8px] px-3 py-2.5 mb-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs font-semibold text-white uppercase">
            NO
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium text-white truncate">NCA Officer</p>
            <p className="text-[11px] text-white/45 truncate">officer@nca.org.gh</p>
          </div>
        </div>
        <button className="flex w-full items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] text-white/50 hover:text-white/80 hover:bg-white/08 transition-colors">
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </aside>
  );
}

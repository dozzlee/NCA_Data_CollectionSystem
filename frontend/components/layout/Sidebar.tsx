"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  BarChart3,
  FileText,
  Building2,
  Calendar,
  ShieldAlert,
  Download,
  LogOut,
  Users,
  PencilLine,
  Menu,
  X,
} from "lucide-react";
import Cookies from "js-cookie";
import { useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/industry-dashboard", label: "Industry Dashboard", icon: BarChart3 },
  { href: "/submissions", label: "Submissions", icon: FileText },
  { href: "/providers", label: "Providers", icon: Building2 },
  { href: "/periods", label: "Periods", icon: Calendar },
  { href: "/compliance", label: "Compliance", icon: ShieldAlert },
  { href: "/exports", label: "Exports", icon: Download },
  { href: "/edit-requests", label: "Edit Requests", icon: PencilLine },
];

function navigationForRole(role?: string) {
  return role === "NCA_ADMIN"
    ? [...NAV_ITEMS, { href: "/users", label: "Users", icon: Users }]
    : NAV_ITEMS.filter((item) => !["/periods"].includes(item.href));
}

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const user = useCurrentUser().data;
  const navItems = navigationForRole(user?.role);

  return (
    <>
      {navItems.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
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
    </>
  );
}

export function Sidebar() {
  const router = useRouter();
  const user = useCurrentUser().data;

  function signOut() {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    router.replace("/login");
  }

  return (
    <aside
      className="hidden h-screen w-[272px] shrink-0 flex-col lg:flex"
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
        <NavigationLinks />
      </nav>

      {/* Footer */}
      <div className="border-t border-white/10 px-3 py-4">
        <div className="flex items-center gap-3 rounded-[8px] px-3 py-2.5 mb-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs font-semibold text-white uppercase">
            NO
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium text-white truncate">{user?.name ?? "NCA User"}</p>
            <p className="text-[11px] text-white/45 truncate">{user?.email}</p>
          </div>
        </div>
        <button onClick={signOut} className="flex w-full items-center gap-3 rounded-[8px] px-3 py-2 text-[13px] text-white/50 hover:text-white/80 hover:bg-white/08 transition-colors">
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </aside>
  );
}

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const user = useCurrentUser().data;

  useEffect(() => setOpen(false), [pathname]);

  function signOut() {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    router.replace("/login");
  }

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-white/10 bg-[#002d5b] px-4 text-white lg:hidden">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] bg-[#E31937] text-[10px] font-bold tracking-wider">
            NCA
          </div>
          <div className="min-w-0">
            <p className="truncate text-[10px] font-semibold uppercase tracking-[0.08em] text-white/50">
              National Communications Authority
            </p>
            <p className="truncate text-[12px] font-semibold">Data Collection System</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-white/15 text-white/80 hover:bg-white/10 hover:text-white"
          aria-label="Open navigation"
          aria-expanded={open}
        >
          <Menu size={18} />
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 z-[80] flex lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation menu">
          <button
            type="button"
            className="absolute inset-0 bg-[#001836]/55"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          />
          <aside className="relative z-10 flex h-full w-[min(88vw,320px)] flex-col bg-[#001836] shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-5">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/45">
                  Signed in as
                </p>
                <p className="mt-0.5 text-[13px] font-medium text-white">{user?.name ?? "NCA User"}</p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-[8px] text-white/65 hover:bg-white/10 hover:text-white"
                aria-label="Close navigation"
              >
                <X size={18} />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto px-3 py-4">
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-white/35">
                Navigation
              </p>
              <div className="space-y-0.5">
                <NavigationLinks onNavigate={() => setOpen(false)} />
              </div>
            </nav>
            <div className="border-t border-white/10 p-3">
              <button
                type="button"
                onClick={signOut}
                className="flex w-full items-center gap-3 rounded-[8px] px-3 py-2.5 text-[13px] text-white/55 hover:bg-white/10 hover:text-white"
              >
                <LogOut size={15} />
                Sign out
              </button>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

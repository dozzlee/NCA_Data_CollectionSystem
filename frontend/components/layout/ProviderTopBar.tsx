"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { FileClock, FileText, LayoutDashboard, LogOut, ShieldCheck } from "lucide-react";
import Cookies from "js-cookie";
import { useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { NotificationBell } from "./NotificationBell";

export function ProviderTopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const userQ = useCurrentUser();
  const user = userQ.data;
  const nav = [
    { href: "/provider/dashboard", label: user?.role === "PROVIDER_APPROVER" ? "Overview" : "My Forms", icon: LayoutDashboard },
    ...(user?.role === "PROVIDER_APPROVER"
      ? [{ href: "/provider/approvals", label: "Pending Approval", icon: ShieldCheck }]
      : []),
    { href: "/provider/history", label: "History", icon: FileClock },
    { href: "/provider/requests", label: "Edit Requests", icon: FileText },
  ];

  function signOut() {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    router.replace("/login");
  }

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
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-[8px] px-3 py-1.5 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-[#eceef0] text-[#191c1e]"
                    : "text-[#43474f] hover:bg-[#f2f4f6] hover:text-[#191c1e]"
                )}
              >
                <Icon size={14} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <NotificationBell />
          <div className="text-right">
            <p className="text-[12px] font-medium text-[#191c1e]">{user?.name ?? "Provider User"}</p>
            <p className="text-[11px] text-[#737780]">{user?.email}</p>
          </div>
          <button onClick={signOut} className="flex items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12px] text-[#737780] hover:bg-[#eceef0] hover:text-[#191c1e] transition-colors">
            <LogOut size={13} />
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

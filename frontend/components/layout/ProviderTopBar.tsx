"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { FileText, LayoutDashboard, LogOut } from "lucide-react";

const NAV = [
  { href: "/provider/dashboard", label: "My Submissions", icon: LayoutDashboard },
  { href: "/provider/submissions", label: "Forms", icon: FileText },
];

export function ProviderTopBar() {
  const pathname = usePathname();

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
          {NAV.map(({ href, label, icon: Icon }) => {
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
          <div className="text-right">
            <p className="text-[12px] font-medium text-[#191c1e]">Provider User</p>
            <p className="text-[11px] text-[#737780]">data@provider.example</p>
          </div>
          <button className="flex items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12px] text-[#737780] hover:bg-[#eceef0] hover:text-[#191c1e] transition-colors">
            <LogOut size={13} />
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

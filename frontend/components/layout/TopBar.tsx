"use client";

import { Search } from "lucide-react";
import { NotificationBell } from "./NotificationBell";

export function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[#e6e8ea] bg-white px-4 sm:px-6">
      {/* Search */}
      <div className="hidden flex-1 max-w-sm items-center gap-2 rounded-[8px] border border-[#c3c6d0] bg-[#f7f9fb] px-3 py-1.5 text-[13px] text-[#43474f] sm:flex">
        <Search size={13} className="shrink-0 text-[#737780]" />
        <input
          type="search"
          placeholder="Search providers, submissions..."
          className="flex-1 bg-transparent outline-none placeholder:text-[#737780] text-[13px]"
        />
      </div>

      <div className="flex items-center gap-2 ml-auto">
        <NotificationBell />

        {/* Period indicator */}
        <div className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] px-2.5 py-1.5 sm:px-3">
          <span className="h-2 w-2 rounded-full bg-[#1f7a4d]" />
          <span className="text-[12px] font-medium text-[#191c1e]">Annual 2025</span>
          <span className="hidden text-[11px] text-[#737780] sm:inline">Active</span>
        </div>
      </div>
    </header>
  );
}

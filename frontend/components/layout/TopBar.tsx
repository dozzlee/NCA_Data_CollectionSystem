"use client";

import { Bell, Search } from "lucide-react";

export function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-[#e6e8ea] bg-white px-6">
      {/* Search */}
      <div className="flex flex-1 max-w-sm items-center gap-2 rounded-[8px] border border-[#c3c6d0] bg-[#f7f9fb] px-3 py-1.5 text-[13px] text-[#43474f]">
        <Search size={13} className="shrink-0 text-[#737780]" />
        <input
          type="search"
          placeholder="Search providers, submissions..."
          className="flex-1 bg-transparent outline-none placeholder:text-[#737780] text-[13px]"
        />
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* Notifications */}
        <button className="relative flex h-8 w-8 items-center justify-center rounded-[8px] text-[#43474f] hover:bg-[#eceef0] transition-colors">
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-[#E31937]" />
        </button>

        {/* Period indicator */}
        <div className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] px-3 py-1.5">
          <span className="h-2 w-2 rounded-full bg-[#1f7a4d]" />
          <span className="text-[12px] font-medium text-[#191c1e]">Annual 2025</span>
          <span className="text-[11px] text-[#737780]">Active</span>
        </div>
      </div>
    </header>
  );
}

"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { SessionTimeoutModal } from "@/components/ui/SessionTimeoutModal";
import { useSessionTimeout } from "@/hooks/useSessionTimeout";
import { refreshAccessToken } from "@/lib/api";

export default function NCALayout({ children }: { children: React.ReactNode }) {
  const { showWarning, handleStaySignedIn, handleSignOut } = useSessionTimeout(refreshAccessToken);

  return (
    <div className="flex h-screen overflow-hidden bg-[#f7f9fb]">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          {children}
        </main>
      </div>
      {showWarning && (
        <SessionTimeoutModal onStaySignedIn={handleStaySignedIn} onSignOut={handleSignOut} />
      )}
    </div>
  );
}

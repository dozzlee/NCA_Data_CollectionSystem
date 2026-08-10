"use client";

import { MobileNavigation, Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { SessionTimeoutModal } from "@/components/ui/SessionTimeoutModal";
import { useSessionTimeout } from "@/hooks/useSessionTimeout";
import { api } from "@/lib/api";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";

async function refreshToken(): Promise<boolean> {
  const refresh = Cookies.get("refresh_token");
  if (!refresh) return false;
  try {
    const data = await api.post<{ access: string }>("/auth/refresh/", { refresh });
    Cookies.set("access_token", data.access, { expires: 1 / 96 });
    return true;
  } catch {
    return false;
  }
}

export default function NCALayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const userQ = useCurrentUser();
  const { showWarning, handleStaySignedIn, handleSignOut } = useSessionTimeout(refreshToken);

  useEffect(() => {
    if (userQ.data && !userQ.data.role.startsWith("NCA_")) router.replace("/provider/dashboard");
  }, [userQ.data, router]);

  if (userQ.isLoading) return <div className="min-h-screen bg-[#f7f9fb]" />;
  if (!userQ.data?.role.startsWith("NCA_")) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-[#f7f9fb]">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <MobileNavigation />
        <TopBar />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
      {showWarning && (
        <SessionTimeoutModal onStaySignedIn={handleStaySignedIn} onSignOut={handleSignOut} />
      )}
    </div>
  );
}

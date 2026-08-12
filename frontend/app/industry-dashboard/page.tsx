"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { IndustryDashboard } from "@/components/industry/IndustryDashboard";
import { ProviderTopBar } from "@/components/layout/ProviderTopBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function IndustryDashboardPage() {
  const router = useRouter();
  const { data: user, isLoading, isError } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => api("/auth/me/"),
    retry: false,
  });

  useEffect(() => {
    if (isError) router.replace("/login");
  }, [isError, router]);

  if (isLoading || !user) {
    return <div className="min-h-screen bg-[#f7f9fb] p-8 text-sm text-[#737780]">Loading…</div>;
  }

  if (user.role.startsWith("PROVIDER")) {
    return (
      <div className="flex min-h-screen flex-col bg-[#f7f9fb]">
        <ProviderTopBar />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <IndustryDashboard canManage={false} />
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#f7f9fb]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <IndustryDashboard canManage={user.role === "NCA_ADMIN" || user.role === "NCA_OFFICER"} />
        </main>
      </div>
    </div>
  );
}

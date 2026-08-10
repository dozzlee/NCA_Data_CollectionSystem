"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ProviderTopBar } from "@/components/layout/ProviderTopBar";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function ProviderLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const userQ = useCurrentUser();

  useEffect(() => {
    if (userQ.data && !userQ.data.role.startsWith("PROVIDER_")) router.replace("/dashboard");
  }, [userQ.data, router]);

  if (userQ.isLoading) return <div className="min-h-screen bg-[#f7f9fb]" />;
  if (!userQ.data?.role.startsWith("PROVIDER_")) return null;

  return (
    <div className="flex min-h-screen flex-col bg-[#f7f9fb]">
      <ProviderTopBar />
      <main className="flex-1 mx-auto w-full max-w-[1200px] px-6 py-8">
        {children}
      </main>
    </div>
  );
}

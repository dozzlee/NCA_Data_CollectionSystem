"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export function RoleRouteGuard({ children, area }: { children: React.ReactNode; area: "NCA" | "PROVIDER" }) {
  const router = useRouter(); const pathname = usePathname();
  const { data: user, isLoading } = useQuery<User>({ queryKey: ["me"], queryFn: () => api("/auth/me/") });
  useEffect(() => {
    if (!user) return;
    const provider = user.role.startsWith("PROVIDER");
    if (area === "NCA" && provider) router.replace("/provider/dashboard");
    else if (area === "PROVIDER" && !provider) router.replace(user.role === "NCA_VIEWER" ? "/data-requests" : "/dashboard");
    else if (user.role === "NCA_VIEWER" && !["/data-catalog", "/data-requests", "/notifications"].some(p => pathname.startsWith(p))) router.replace("/data-requests");
  }, [area, pathname, router, user]);
  if (isLoading || !user) return <div className="p-8 text-sm text-[#737780]">Loading…</div>;
  return <>{children}</>;
}

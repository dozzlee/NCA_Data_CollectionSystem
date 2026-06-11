"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, RadioTower, Search, ShieldCheck, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { PROVIDER_CATEGORY_LABELS, formatDate } from "@/lib/utils";
import type { PaginatedResponse, ProviderCategory, ProviderProfile, ProviderStatus } from "@/lib/types";

const PROVIDER_STATUSES: ProviderStatus[] = ["ACTIVE", "INACTIVE", "SUSPENDED", "ARCHIVED"];

function statusVariant(status: ProviderStatus) {
  if (status === "ACTIVE") return "success";
  if (status === "SUSPENDED") return "warning";
  if (status === "ARCHIVED") return "muted";
  return "default";
}

export default function ProvidersPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<ProviderCategory | "">("");
  const [status, setStatus] = useState<ProviderStatus | "">("");

  const params = useMemo(() => {
    const qs = new URLSearchParams();
    if (search) qs.set("search", search);
    if (category) qs.set("category", category);
    if (status) qs.set("status", status);
    return qs.toString();
  }, [search, category, status]);

  const providersQ = useQuery({
    queryKey: ["providers", params],
    queryFn: () => api.get<PaginatedResponse<ProviderProfile>>(`/providers/${params ? `?${params}` : ""}`),
  });

  const providers = providersQ.data?.results ?? [];
  const activeCount = providers.filter((p) => p.status === "ACTIVE").length;
  const overdueCount = providers.reduce((sum, p) => sum + (p.overdue_count ?? 0), 0);
  const expectedCount = providers.reduce((sum, p) => sum + (p.expected_count ?? 0), 0);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Providers</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">Licensed operators and their current submission load</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Visible Providers", value: providersQ.data?.count ?? 0, icon: Building2, color: "#0066cc" },
          { label: "Active", value: activeCount, icon: ShieldCheck, color: "#1f7a4d" },
          { label: "Expected Returns", value: expectedCount, icon: RadioTower, color: "#002d5b" },
          { label: "Overdue Returns", value: overdueCount, icon: AlertTriangle, color: "#E31937" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-[16px] bg-white border border-[#e6e8ea] p-5"
            style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{label}</p>
              <div className="h-8 w-8 flex items-center justify-center rounded-[8px]" style={{ background: color + "18" }}>
                <Icon size={14} style={{ color }} />
              </div>
            </div>
            {providersQ.isLoading ? <Skeleton className="h-8 w-12" /> : (
              <p className="text-[28px] font-semibold tabular-nums text-[#191c1e]">{value}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] min-w-[240px]">
          <Search size={13} className="text-[#737780] shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search provider, licence, email..."
            className="flex-1 bg-transparent outline-none text-[13px] text-[#191c1e] placeholder:text-[#737780]"
          />
        </div>

        <select value={category} onChange={(e) => setCategory(e.target.value as ProviderCategory | "")}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All categories</option>
          {Object.entries(PROVIDER_CATEGORY_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        <select value={status} onChange={(e) => setStatus(e.target.value as ProviderStatus | "")}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All statuses</option>
          {PROVIDER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="rounded-[16px] bg-white border border-[#e6e8ea] overflow-hidden"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#eceef0] bg-[#f7f9fb]">
                {["Provider", "Category", "Licence", "Primary Contact", "Submissions", "Status"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {providersQ.isLoading ? (
                Array.from({ length: 7 }).map((_, i) => (
                  <tr key={i} className="border-b border-[#eceef0]">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-5 py-3"><Skeleton className="h-4 w-full max-w-[140px]" /></td>
                    ))}
                  </tr>
                ))
              ) : !providers.length ? (
                <tr><td colSpan={6} className="px-5 py-14 text-center text-[13px] text-[#737780]">No providers match the current filters.</td></tr>
              ) : providers.map((provider) => (
                <tr key={provider.id} className="border-b border-[#eceef0] last:border-0 hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3">
                    <p className="text-[13px] font-medium text-[#191c1e] max-w-[220px] truncate">{provider.registered_name}</p>
                    <p className="text-[11px] text-[#737780]">{provider.trade_name || "No trade name"}</p>
                  </td>
                  <td className="px-5 py-3 text-[12px] text-[#43474f]">
                    {PROVIDER_CATEGORY_LABELS[provider.category] ?? provider.category}
                  </td>
                  <td className="px-5 py-3">
                    <p className="text-[12px] font-mono font-medium text-[#002d5b]">{provider.licence_number}</p>
                    <p className="text-[11px] text-[#737780]">
                      Expires {provider.licence_expiry_date ? formatDate(provider.licence_expiry_date) : "not set"}
                    </p>
                  </td>
                  <td className="px-5 py-3">
                    <p className="text-[12px] text-[#191c1e]">{provider.primary_email}</p>
                    <p className="text-[11px] text-[#737780]">{provider.primary_phone}</p>
                  </td>
                  <td className="px-5 py-3">
                    <p className="text-[12px] tabular-nums text-[#43474f]">{provider.expected_count ?? 0} expected</p>
                    <p className="text-[11px] tabular-nums text-[#737780]">{provider.overdue_count ?? 0} overdue</p>
                  </td>
                  <td className="px-5 py-3"><Badge variant={statusVariant(provider.status)}>{provider.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {providersQ.data && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-[#eceef0]">
            <p className="text-[12px] text-[#737780]">{providersQ.data.count} total · showing {providers.length}</p>
          </div>
        )}
      </div>
    </div>
  );
}

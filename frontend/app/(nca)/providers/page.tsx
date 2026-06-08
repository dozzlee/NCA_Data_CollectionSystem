"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ProviderProfile, ProviderCategory, ProviderStatus } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

const STATUS_COLORS: Record<ProviderStatus, string> = {
  ACTIVE: "bg-[#e5f4eb] text-[#1f7a4d]",
  INACTIVE: "bg-[#f2f4f6] text-[#43474f]",
  SUSPENDED: "bg-[#fff3bf] text-[#7a5c00]",
  ARCHIVED: "bg-[#f2f4f6] text-[#737780]",
};

const CATEGORIES: ProviderCategory[] = ["MNO", "ISP", "PAY_TV", "TOWER_OPERATOR", "TOWER_MAIN", "DOMESTIC_FIBRE", "SUBMARINE_FIBRE"];
const STATUSES: ProviderStatus[] = ["ACTIVE", "INACTIVE", "SUSPENDED", "ARCHIVED"];

export default function ProvidersPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");

  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (category) params.set("category", category);
  if (status) params.set("status", status);

  const { data, isLoading } = useQuery<{ results: ProviderProfile[] }>({
    queryKey: ["providers", search, category, status],
    queryFn: () => api(`/providers/?${params}`),
  });

  const providers = data?.results ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">Providers</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">Licensed operators registered in the system.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search by name, licence number…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20 w-64"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none"
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{PROVIDER_CATEGORY_LABELS[c]}</option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <table className="w-full text-left">
          <thead className="border-b border-[#eceef0] bg-[#f7f9fb]">
            <tr>
              {["Provider", "Category", "Licence No.", "Email", "Phone", "Status", ""].map((h) => (
                <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eceef0]">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-5 py-3.5">
                        <Skeleton className="h-3.5 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              : providers.length === 0
              ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-[14px] text-[#737780]">
                    No providers found.
                  </td>
                </tr>
              )
              : providers.map((p) => (
                <tr key={p.id} className="hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-medium text-[#191c1e]">{p.registered_name}</p>
                    {p.trade_name && <p className="text-[11px] text-[#737780]">{p.trade_name}</p>}
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{PROVIDER_CATEGORY_LABELS[p.category]}</td>
                  <td className="px-5 py-3.5 text-[13px] font-mono text-[#43474f]">{p.licence_number}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{p.primary_email}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{p.primary_phone}</td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STATUS_COLORS[p.status]}`}>
                      {p.status.charAt(0) + p.status.slice(1).toLowerCase()}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <Link
                      href={`/providers/${p.id}`}
                      className="text-[13px] font-medium text-[#0066cc] hover:underline"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

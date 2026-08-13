"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission, PaginatedResponse } from "@/lib/types";

export default function ProviderHistoryPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useQuery<PaginatedResponse<ExpectedSubmission>>({
    queryKey: ["provider-history", search],
    queryFn: () => api(`/provider-workspace/submissions/?queue=history&ordering=-created_at${search ? `&search=${encodeURIComponent(search)}` : ""}`),
  });
  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Submission history</h1><p className="mt-1 text-sm text-[#43474f]">Official versions, review progress, approval decisions and receipts for your provider.</p></div>
    <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search form or period" className="w-full max-w-md rounded-lg border bg-white px-3 py-2 text-sm" />
    <div className="overflow-x-auto rounded-2xl border bg-white"><table className="w-full min-w-[840px] text-left"><thead className="border-b bg-[#f7f9fb]"><tr>{["Form", "Period", "Submitted", "Responsible approver", "Status", "Receipt", ""].map((h) => <th key={h} className="px-5 py-3 text-xs font-semibold uppercase text-[#43474f]">{h}</th>)}</tr></thead>
      <tbody className="divide-y">{isLoading ? Array.from({ length: 5 }).map((_, i) => <tr key={i}>{Array.from({ length: 7 }).map((__, j) => <td key={j} className="px-5 py-4"><Skeleton className="h-4" /></td>)}</tr>)
      : !data?.results.length ? <tr><td colSpan={7} className="p-12 text-center text-sm text-[#737780]">No submission history yet.</td></tr>
      : data.results.map((row) => <tr key={row.id}><td className="px-5 py-4"><p className="text-sm font-medium">{row.form_name}</p><p className="font-mono text-xs text-[#737780]">{row.form_code}</p></td><td className="px-5 py-4 text-sm">{row.period_name}</td><td className="px-5 py-4 text-sm text-[#737780]">{row.submitted_at ? new Date(row.submitted_at).toLocaleString() : "—"}</td><td className="px-5 py-4 text-sm">{row.last_edited_by_name || "—"}</td><td className="px-5 py-4"><WorkflowBadge status={row.workflow_status} /></td><td className="px-5 py-4 text-sm">{row.receipt_available ? row.receipt_reference : "—"}</td><td className="px-5 py-4"><Link href={`/provider/submissions/${row.id}`} className="text-sm font-medium text-[#0066cc]">View →</Link></td></tr>)}</tbody>
    </table></div>
  </div>;
}

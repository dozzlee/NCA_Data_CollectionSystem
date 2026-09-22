"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatTransmissionDateTime } from "@/lib/utils";
import type { FormalSubmission, PaginatedResponse } from "@/lib/types";

export default function ProviderHistoryPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useQuery<PaginatedResponse<FormalSubmission>>({
    queryKey: ["provider-history", search],
    queryFn: () => api(`/provider-submissions/${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  });
  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Submissions</h1><p className="mt-1 text-sm text-[#43474f]">One current row per assigned form, with every immutable submission version retained below it.</p></div>
    <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search form or period" className="w-full max-w-md rounded-lg border bg-white px-3 py-2 text-sm" />
    <div className="overflow-x-auto rounded-2xl border bg-white"><table className="w-full min-w-[940px] text-left"><thead className="border-b bg-[#f7f9fb]"><tr>{["Form", "Version", "Period", "Current status", "Latest transmission", "Latest communication", ""].map((h) => <th key={h} className="px-5 py-3 text-xs font-semibold uppercase text-[#43474f]">{h}</th>)}</tr></thead>
      <tbody className="divide-y">{isLoading ? Array.from({ length: 5 }).map((_, i) => <tr key={i}>{Array.from({ length: 7 }).map((__, j) => <td key={j} className="px-5 py-4"><Skeleton className="h-4" /></td>)}</tr>)
      : !data?.results.length ? <tr><td colSpan={7} className="p-12 text-center text-sm text-[#737780]">No formal submissions yet. Forms appear here after a Provider Approver sends them to NCA.</td></tr>
      : data.results.map((row) => <tr key={row.form_task_id??row.id}>
        <td className="px-5 py-4"><p className="text-sm font-medium">{row.form_name}</p><p className="font-mono text-xs text-[#737780]">{row.form_code}</p><p className="mt-1 max-w-[260px] break-all font-mono text-[10px] text-[#004999]">{row.submission_reference}</p></td>
        <td className="px-5 py-4 text-sm"><p>v{row.version}</p>{(row.formal_versions?.length??0)>1&&<p className="mt-1 text-[10px] text-[#737780]">History: {row.formal_versions!.map((item,index)=><span key={item.id}>{index>0?" · ":""}<Link href={`/provider/history/${item.id}`} className="font-semibold text-[#0066cc]">v{item.version}</Link></span>)}</p>}</td>
        <td className="px-5 py-4 text-sm">{row.period_name}</td><td className="px-5 py-4">{row.provider_display_status === "FLAGGED" ? <span className="inline-flex rounded-full bg-[#ffe8e8] px-2.5 py-0.5 text-[11px] font-semibold text-[#b3261e]">Flagged</span> : <WorkflowBadge status={row.regulatory_status as any} />}</td>
        <td className="whitespace-nowrap px-5 py-4 text-sm text-[#43474f]">{row.submitted_at ? formatTransmissionDateTime(row.submitted_at) : row.latest_action_at ? formatTransmissionDateTime(row.latest_action_at) : "—"}</td>
        <td className="max-w-[280px] px-5 py-4">{row.latest_message ? <><p className="truncate text-sm font-semibold text-[#191c1e]" title={row.latest_message.subject}>{row.latest_message.subject}</p>{row.latest_message.preview && <p className="mt-0.5 truncate text-xs text-[#737780]" title={row.latest_message.body}>{row.latest_message.preview}</p>}</> : <span className="text-sm text-[#737780]">No communication</span>}</td>
        <td className="px-5 py-4">{row.latest_submission_id?<Link href={`/provider/history/${row.latest_submission_id}`} className="text-sm font-medium text-[#0066cc]">View →</Link>:<span className="text-sm text-[#737780]">Unavailable</span>}</td>
      </tr>)}</tbody>
    </table></div>
  </div>;
}

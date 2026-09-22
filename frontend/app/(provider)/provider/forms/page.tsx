"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission, PaginatedResponse, ProviderFormStatus } from "@/lib/types";

const STATUS_LABELS: Record<ProviderFormStatus, string> = {
  IN_PROGRESS: "In Progress",
  AWAITING_APPROVAL: "Awaiting Approval",
  CORRECTIONS_REQUIRED: "Corrections Required",
  CLOSED: "Closed",
};

export default function ProviderFormsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | ProviderFormStatus>("");
  const query = useQuery<PaginatedResponse<ExpectedSubmission>>({
    queryKey: ["provider-forms", search, status],
    queryFn: () => api(`/provider-workspace/forms/?${new URLSearchParams({
      ...(search ? { search } : {}), ...(status ? { provider_status: status } : {}),
    }).toString()}`),
  });

  return <div className="space-y-6">
    <div>
      <h1 className="text-[28px] font-semibold text-[#191c1e]">Internal Review</h1>
      <p className="mt-1 text-sm text-[#43474f]">Active forms being completed, checked or corrected inside your organisation.</p>
    </div>
    <div className="flex flex-wrap gap-3">
      <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search form or reporting period" className="min-w-[260px] flex-1 rounded-lg border bg-white px-3 py-2 text-sm" />
      <select aria-label="Filter forms by stage" value={status} onChange={(event) => setStatus(event.target.value as "" | ProviderFormStatus)} className="rounded-lg border bg-white px-3 py-2 text-sm">
        <option value="">All active stages</option>
        <option value="IN_PROGRESS">In Progress</option>
        <option value="AWAITING_APPROVAL">Awaiting Approval</option>
        <option value="CORRECTIONS_REQUIRED">Corrections Required</option>
      </select>
    </div>
    <div className="overflow-x-auto rounded-2xl border border-[#e6e8ea] bg-white">
      <table className="w-full min-w-[1100px] text-left">
        <thead className="border-b bg-[#f7f9fb]"><tr>{["Form", "Reporting period", "Received", "Deadline", "Status", "Latest message", "Last update", ""].map((heading) => <th key={heading} className="px-5 py-3 text-xs font-semibold uppercase text-[#43474f]">{heading}</th>)}</tr></thead>
        <tbody className="divide-y">
          {query.isLoading ? Array.from({length: 4}).map((_, row) => <tr key={row}>{Array.from({length: 8}).map((__, cell) => <td key={cell} className="px-5 py-4"><Skeleton className="h-4" /></td>)}</tr>)
          : query.isError ? <tr><td colSpan={8} className="p-10 text-center text-sm text-[#c5221f]">Forms could not be loaded. <button onClick={() => query.refetch()} className="font-semibold underline">Retry</button></td></tr>
          : !query.data?.results.length ? <tr><td colSpan={8} className="p-12 text-center text-sm text-[#737780]">No active forms match this view.</td></tr>
          : query.data.results.map((form) => <tr key={form.id}>
            <td className="px-5 py-4"><p className="font-medium">{form.form_name}</p><p className="mt-1 font-mono text-[11px] text-[#004999]">{form.form_reference}</p></td>
            <td className="px-5 py-4 text-sm">{form.period_name}</td>
            <td className="px-5 py-4 text-sm text-[#737780]">{new Date(form.sent_at || form.created_at).toLocaleDateString()}</td>
            <td className="px-5 py-4 text-sm"><DueStateBadge state={form.due_state}/><p className="mt-1 text-xs text-[#737780]">{new Date(form.effective_due_at).toLocaleDateString()}</p></td>
            <td className="px-5 py-4"><span className="rounded-full bg-[#edf4fb] px-2.5 py-1 text-xs font-semibold text-[#004999]">{STATUS_LABELS[form.provider_status]}</span></td>
            <td className="max-w-[260px] px-5 py-4"><p className="text-sm font-medium">{form.latest_message?.subject || "No message"}</p>{form.latest_message?.preview&&<p className="mt-1 line-clamp-2 text-xs text-[#737780]">{form.latest_message.preview}</p>}</td>
            <td className="px-5 py-4 text-sm text-[#737780]">{form.last_edited_at ? new Date(form.last_edited_at).toLocaleString() : new Date(form.created_at).toLocaleString()}</td>
            <td className="px-5 py-4"><Link href={`/provider/forms/${form.id}`} className="inline-flex rounded-lg bg-[#002d5b] px-4 py-2 text-sm font-semibold text-white">{form.permitted_actions.includes("EDIT") ? "Open form" : "View progress"}</Link></td>
          </tr>)}
        </tbody>
      </table>
    </div>
  </div>;
}

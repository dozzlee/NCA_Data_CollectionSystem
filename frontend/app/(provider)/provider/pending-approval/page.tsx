"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission, PaginatedResponse, User } from "@/lib/types";

export default function PendingApprovalPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [deadline, setDeadline] = useState("");
  const { data: user } = useQuery<User>({ queryKey: ["me"], queryFn: () => api("/auth/me/") });
  const query = new URLSearchParams({ queue: "action_required", ordering: "period__due_at" });
  if (search) query.set("search", search);
  if (status) query.set("status", status);
  if (deadline) query.set("deadline", deadline);
  const { data, isLoading, error } = useQuery<PaginatedResponse<ExpectedSubmission>>({
    queryKey: ["provider-approval-queue", search, status, deadline],
    queryFn: () => api(`/provider-workspace/submissions/?${query}`),
    enabled: user?.role === "PROVIDER_APPROVER",
  });
  if (user && user.role !== "PROVIDER_APPROVER") return <div className="rounded-2xl border bg-white p-8"><h1 className="text-xl font-semibold">Provider Approver access required</h1><p className="mt-2 text-sm text-[#737780]">Data Entry users work from their shared dashboard.</p></div>;

  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Approval work queue</h1><p className="mt-1 text-sm text-[#43474f]">Review complete data, correct permitted values, return targeted work or submit with an accuracy attestation.</p></div>
    <div className="grid gap-3 rounded-xl border bg-white p-4 md:grid-cols-[1fr_220px_180px]">
      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search form or period" className="rounded-lg border px-3 py-2 text-sm" />
      <select aria-label="Approval stage" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border px-3 py-2 text-sm"><option value="">All approval stages</option><option value="PENDING_APPROVAL">First approval</option><option value="PROVIDER_RESUBMITTED">Returned work</option><option value="CORRECTION_REQUESTED">NCA correction</option></select>
      <select aria-label="Deadline state" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="rounded-lg border px-3 py-2 text-sm"><option value="">Any deadline</option><option value="OVERDUE">Overdue</option><option value="DUE_SOON">Due soon</option><option value="DUE_TODAY">Due today</option></select>
    </div>
    {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">The approval queue could not be loaded. Retry or contact technical support if this persists.</div>}
    {isLoading ? <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}</div>
    : !data?.results.length ? <div className="rounded-2xl border-2 border-dashed py-16 text-center"><p className="font-medium">No matching approval work</p><p className="mt-1 text-sm text-[#737780]">Change the filters or wait for Data Entry to submit a return.</p></div>
    : <div className="space-y-3">{data.results.map((row) => <article key={row.id} className="rounded-2xl border bg-white p-5">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div><div className="flex flex-wrap items-center gap-2"><WorkflowBadge status={row.workflow_status} /><DueStateBadge state={row.due_state} /></div><h2 className="mt-2 font-semibold">{row.form_name}</h2><p className="text-sm text-[#737780]">{row.period_name} · {Number(row.completion_pct).toFixed(0)}% complete · {row.open_correction_count} open corrections</p><p className="mt-2 text-xs text-[#43474f]">Last edited by {row.last_edited_by_name || "Data Entry"}{row.last_edited_at ? ` on ${new Date(row.last_edited_at).toLocaleString()}` : ""}</p></div>
        <Link href={`/provider/submissions/${row.id}`} className="rounded-lg bg-[#001836] px-5 py-2.5 text-center text-sm font-semibold text-white">Review submission</Link>
      </div>
    </article>)}</div>}
  </div>;
}

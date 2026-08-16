"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission, PaginatedResponse, ProviderWorkspaceSummary, User } from "@/lib/types";

function displayDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";
}

export default function ProviderDashboardPage() {
  const { data: user } = useQuery<User>({ queryKey: ["me"], queryFn: () => api("/auth/me/"), staleTime: 300_000 });
  const isApprover = user?.role === "PROVIDER_APPROVER";
  const { data: summary, isLoading: summaryLoading } = useQuery<ProviderWorkspaceSummary>({
    queryKey: ["provider-workspace-summary"], queryFn: () => api("/provider-workspace/summary/"),
  });
  const { data, isLoading } = useQuery<PaginatedResponse<ExpectedSubmission>>({
    queryKey: ["provider-workspace", "action_required"],
    queryFn: () => api("/provider-workspace/submissions/?queue=action_required&ordering=period__due_at&page_size=20"),
  });
  const awaitingDataEntry = useQuery<PaginatedResponse<ExpectedSubmission>>({
    queryKey: ["provider-workspace", "awaiting_data_entry"],
    queryFn: () => api("/provider-workspace/submissions/?queue=awaiting_data_entry&ordering=period__due_at&page_size=20"),
    enabled: isApprover,
  });
  const cards = isApprover ? [
    ["Awaiting Data Entry", summary?.awaiting_data_entry ?? 0],
    ["Awaiting approval", summary?.awaiting_approver ?? 0],
    ["NCA corrections", summary?.nca_corrections ?? 0],
    ["Returned to Data Entry", summary?.returned_to_data_entry ?? 0],
    ["Overdue", summary?.overdue ?? 0],
  ] : [
    ["Action required", summary?.action_required ?? 0],
    ["Drafts", summary?.drafts ?? 0],
    ["Due soon", summary?.due_soon ?? 0],
    ["Overdue", summary?.overdue ?? 0],
  ];
  const rows = data?.results ?? [];

  return <div className="space-y-7">
    <div>
      <h1 className="text-[28px] font-semibold text-[#191c1e]">{isApprover ? "Approver workspace" : "Data Entry workspace"}</h1>
      <p className="mt-1 text-sm text-[#43474f]">{isApprover
        ? "Review returns, manage NCA corrections and submit verified data to NCA."
        : "Shared work for your provider. Any Data Entry colleague can continue an editable return."}</p>
    </div>

    {summary?.overdue ? <div className="rounded-xl border border-[#e31937]/30 bg-[#ffe8e8] px-5 py-4 text-sm text-[#9b1c1c]">
      <strong>{summary.overdue} overdue return{summary.overdue === 1 ? "" : "s"}.</strong> Open the work item to see its current blocker and next action.
    </div> : null}

    <div className={`grid grid-cols-2 gap-4 ${isApprover ? "lg:grid-cols-5" : "lg:grid-cols-4"}`}>
      {summaryLoading ? Array.from({ length: isApprover ? 5 : 4 }).map((_, index) => <Skeleton key={index} className="h-24 rounded-xl" />) : cards.map(([label, count]) =>
        <div key={label} className="rounded-xl border border-[#e6e8ea] bg-white p-5">
          <p className="text-3xl font-bold text-[#002d5b]">{count}</p><p className="mt-1 text-xs font-semibold uppercase tracking-wide text-[#737780]">{label}</p>
        </div>)}
    </div>

    <section className="overflow-hidden rounded-2xl border border-[#e6e8ea] bg-white">
      <div className="flex items-center justify-between border-b border-[#eceef0] px-6 py-4">
        <div><h2 className="font-semibold text-[#191c1e]">Action required</h2><p className="text-xs text-[#737780]">Server-calculated queue across every provider return</p></div>
        {isApprover && <Link href="/provider/pending-approval" className="text-sm font-medium text-[#0066cc]">Open full queue →</Link>}
      </div>
      {isLoading ? <div className="space-y-3 p-6">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
      : rows.length === 0 ? <div className="p-12 text-center"><p className="font-medium text-[#191c1e]">Nothing needs your action</p><p className="mt-1 text-sm text-[#737780]">New drafts, approval work and corrections will appear here.</p></div>
      : <div className="divide-y divide-[#eceef0]">{rows.map((row) => <article key={row.id} className="grid gap-4 px-6 py-4 md:grid-cols-[1fr_auto] md:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h3 className="font-medium text-[#191c1e]">{row.form_name}</h3><WorkflowBadge status={row.workflow_status} /><DueStateBadge state={row.due_state} /></div>
          <p className="mt-1 text-xs text-[#737780]">{row.period_name} · Effective deadline {displayDate(row.effective_due_at)}</p>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#43474f]">
            <span>{Number(row.completion_pct).toFixed(0)}% complete</span>
            <span>{row.open_correction_count} open correction{row.open_correction_count === 1 ? "" : "s"}</span>
            <span>Last edit: {row.last_edited_by_name || "Not edited"}{row.last_edited_at ? ` · ${new Date(row.last_edited_at).toLocaleString()}` : ""}</span>
          </div>
        </div>
        <Link href={`/provider/submissions/${row.id}`} className="rounded-lg bg-[#002d5b] px-4 py-2 text-center text-sm font-semibold text-white">
          {row.permitted_actions.includes("EDIT") ? "Open and work" : "Review"}
        </Link>
      </article>)}</div>}
    </section>

    {isApprover && <section className="overflow-hidden rounded-2xl border border-[#e6e8ea] bg-white">
      <div className="border-b border-[#eceef0] px-6 py-4"><h2 className="font-semibold text-[#191c1e]">Awaiting Data Entry</h2><p className="text-xs text-[#737780]">Track newly assigned forms. Data Entry owns editing until it submits the form for approval.</p></div>
      {awaitingDataEntry.isLoading ? <div className="space-y-3 p-6">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
      : !(awaitingDataEntry.data?.results.length) ? <div className="p-10 text-center text-sm text-[#737780]">No forms are currently awaiting Data Entry.</div>
      : <div className="divide-y divide-[#eceef0]">{awaitingDataEntry.data.results.map(row => <article key={row.id} className="grid gap-4 px-6 py-4 md:grid-cols-[1fr_auto] md:items-center">
        <div><div className="flex flex-wrap items-center gap-2"><h3 className="font-medium text-[#191c1e]">{row.form_name}</h3><WorkflowBadge status={row.workflow_status} /><DueStateBadge state={row.due_state} /></div><p className="mt-1 text-xs text-[#737780]">{row.period_name} · {Number(row.completion_pct).toFixed(0)}% complete · Data Entry action required</p></div>
        <Link href={`/provider/submissions/${row.id}`} className="rounded-lg border border-[#c3c6d0] px-4 py-2 text-center text-sm font-semibold text-[#43474f]">View progress</Link>
      </article>)}</div>}
    </section>}
  </div>;
}

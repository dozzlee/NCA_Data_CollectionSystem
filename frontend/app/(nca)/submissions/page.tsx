"use client";

import { Suspense, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useExpectedSubmissions } from "@/hooks/useDashboard";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate, WORKFLOW_LABELS, DUE_STATE_LABELS, PROVIDER_CATEGORY_LABELS, getDueStateRowBg } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import type { DueState, WorkflowStatus } from "@/lib/types";

const STATUS_FILTERS: WorkflowStatus[] = [
  "NOT_STARTED", "DRAFT", "PENDING_APPROVAL", "SUBMITTED",
  "UNDER_REVIEW", "CORRECTION_REQUESTED", "APPROVED", "REJECTED",
];
const DUE_STATE_FILTERS: DueState[] = ["OPEN", "DUE_SOON", "DUE_TODAY", "OVERDUE", "CLOSED"];

function SubmissionsPageContent() {
  const searchParams = useSearchParams();
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | "">((searchParams.get("workflow_status") as WorkflowStatus) ?? "");
  const [dueStateFilter, setDueStateFilter] = useState<DueState | "">((searchParams.get("due_state") as DueState) ?? "");
  const [categoryFilter, setCategoryFilter] = useState(searchParams.get("provider__category") ?? "");

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (statusFilter) p.workflow_status = statusFilter;
    if (dueStateFilter) p.due_state = dueStateFilter;
    if (categoryFilter) p.provider__category = categoryFilter;
    return p;
  }, [statusFilter, dueStateFilter, categoryFilter]);

  const { data, isLoading } = useExpectedSubmissions(params);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Submissions</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">All provider form submissions across reporting periods</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as WorkflowStatus | "")}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All statuses</option>
          {STATUS_FILTERS.map((s) => <option key={s} value={s}>{WORKFLOW_LABELS[s]}</option>)}
        </select>

        <select value={dueStateFilter} onChange={(e) => setDueStateFilter(e.target.value as DueState | "")}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All due states</option>
          {DUE_STATE_FILTERS.map((s) => <option key={s} value={s}>{DUE_STATE_LABELS[s]}</option>)}
        </select>

        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All categories</option>
          {Object.entries(PROVIDER_CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        {data && <p className="ml-auto text-[12px] text-[#737780]">{data.count} results</p>}
      </div>

      {/* Table */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea] overflow-hidden"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#eceef0] bg-[#f7f9fb]">
              {["Provider", "Form", "Period", "Due Date", "Status", "Due State", ""].map((h) => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-[#eceef0]">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-5 py-3"><Skeleton className="h-4 w-full max-w-[120px]" /></td>
                    ))}
                  </tr>
                ))
              : !data?.results.length
              ? <tr><td colSpan={7} className="px-5 py-14 text-center text-[13px] text-[#737780]">No submissions match the current filters.</td></tr>
              : data.results.map((sub) => (
                  <tr key={sub.id}
                    onClick={() => window.location.href = `/submissions/${sub.id}/review`}
                    className={`border-b border-[#eceef0] last:border-0 hover:brightness-[0.97] transition-colors cursor-pointer group ${getDueStateRowBg(sub.due_state, sub.workflow_status)}`}>
                    <td className="px-5 py-3">
                      <p className="text-[13px] font-medium text-[#191c1e] max-w-[160px] truncate">{sub.provider_name}</p>
                      <p className="text-[11px] text-[#737780]">{PROVIDER_CATEGORY_LABELS[sub.provider_category] ?? sub.provider_category}</p>
                    </td>
                    <td className="px-5 py-3">
                      <p className="text-[12px] font-mono font-medium text-[#002d5b]">{sub.form_code}</p>
                    </td>
                    <td className="px-5 py-3 text-[12px] text-[#43474f]">{sub.period_name}</td>
                    <td className="px-5 py-3 text-[12px] tabular-nums text-[#43474f]">
                      {sub.due_at ? formatDate(sub.due_at) : "—"}
                    </td>
                    <td className="px-5 py-3"><WorkflowBadge status={sub.workflow_status} /></td>
                    <td className="px-5 py-3"><DueStateBadge state={sub.due_state} /></td>
                    <td className="px-5 py-3">
                      <Link href={`/submissions/${sub.id}/review`}
                        className="flex items-center gap-1 text-[12px] font-medium text-[#0066cc] hover:text-[#002d5b] transition-colors">
                        Review <ChevronRight size={12} />
                      </Link>
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function SubmissionsPage() {
  return (
    <Suspense fallback={null}>
      <SubmissionsPageContent />
    </Suspense>
  );
}

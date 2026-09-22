"use client";

import { Suspense, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate, formatTransmissionDateTime, WORKFLOW_LABELS, DUE_STATE_LABELS, PROVIDER_CATEGORY_LABELS, SECTOR_LABELS, getDueStateRowBg } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import type { DueState, ExpectedSubmission, PaginatedResponse, WorkflowStatus } from "@/lib/types";

const STATUS_FILTERS: WorkflowStatus[] = [
  "SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED",
];
const DUE_STATE_FILTERS: DueState[] = ["OPEN", "DUE_SOON", "DUE_TODAY", "OVERDUE", "CLOSED"];

function SubmissionsPageContent() {
  const searchParams = useSearchParams();
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | "">((searchParams.get("workflow_status") as WorkflowStatus) ?? "");
  const [dueStateFilter, setDueStateFilter] = useState<DueState | "">((searchParams.get("due_state") as DueState) ?? "");
  const [categoryFilter, setCategoryFilter] = useState(searchParams.get("provider__category") ?? "");
  const [sectorFilter, setSectorFilter] = useState(searchParams.get("provider__sector") ?? "");
  const attentionRequired = searchParams.get("attention_required") === "true";
  const [flagStatus, setFlagStatus] = useState(searchParams.get("compliance_status") ?? "");
  const [flagType, setFlagType] = useState(searchParams.get("compliance_flag_type") ?? "");

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (statusFilter) p.workflow_status = statusFilter;
    if (dueStateFilter) p.due_state = dueStateFilter;
    if (sectorFilter) p.provider__sector = sectorFilter;
    if (categoryFilter) p.provider__category = categoryFilter;
    if (attentionRequired) p.attention_required = "true";
    if (flagStatus) p.compliance_status = flagStatus;
    if (flagType) p.compliance_flag_type = flagType;
    return p;
  }, [statusFilter, dueStateFilter, categoryFilter, sectorFilter, attentionRequired, flagStatus, flagType]);

  const { data, isLoading } = useQuery<PaginatedResponse<ExpectedSubmission>>({
    queryKey: ["nca-submissions", params],
    queryFn: () => api(`/expected-submissions/?${new URLSearchParams(params).toString()}`),
  });

  const sortedSubmissions = useMemo(() => [...(data?.results ?? [])].sort((a, b) => {
    const aTimestamp = a.latest_action_at ?? a.latest_message?.created_at;
    const bTimestamp = b.latest_action_at ?? b.latest_message?.created_at;
    if (!aTimestamp && !bTimestamp) return b.id - a.id;
    if (!aTimestamp) return 1;
    if (!bTimestamp) return -1;
    return new Date(bTimestamp).getTime() - new Date(aTimestamp).getTime();
  }), [data?.results]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Compliance & Submission</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">Submission progress, compliance flags and review status across reporting periods</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select value={sectorFilter} onChange={(e) => setSectorFilter(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All sectors</option>
          {Object.entries(SECTOR_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
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

        <select value={flagStatus} onChange={(e) => setFlagStatus(e.target.value)} className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e]">
          <option value="">All flag statuses</option><option value="OPEN">Open</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option>
        </select>
        <select value={flagType} onChange={(e) => setFlagType(e.target.value)} className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e]">
          <option value="">All flag types</option><option value="MISSING_DATA">Missing data</option><option value="OVERDUE">Overdue</option><option value="INCOMPLETE">Incomplete</option><option value="CORRECTION">Flag request</option>
        </select>
        {data && <p className="ml-auto text-[12px] text-[#737780]">{data.count} results</p>}
      </div>

      {/* Table */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea] overflow-hidden"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <div className="overflow-x-auto"><table className="w-full min-w-[1320px]">
          <thead>
            <tr className="border-b border-[#eceef0] bg-[#f7f9fb]">
              {["Provider", "Form", "Period", "Due Date", "Current status", "Latest transmission", "Latest communication", "Compliance", "Due State", ""].map((h) => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-[#eceef0]">
                    {Array.from({ length: 10 }).map((_, j) => (
                      <td key={j} className="px-5 py-3"><Skeleton className="h-4 w-full max-w-[120px]" /></td>
                    ))}
                  </tr>
                ))
              : !sortedSubmissions.length
              ? <tr><td colSpan={10} className="px-5 py-14 text-center text-[13px] text-[#737780]">No submissions match the current filters.</td></tr>
              : sortedSubmissions.map((sub) => (
                  <tr key={sub.id}
                    onClick={sub.latest_submission_id ? () => window.location.href = `/submissions/${sub.latest_submission_id}/review` : undefined}
                    className={`border-b border-[#eceef0] last:border-0 transition-colors group ${sub.latest_submission_id ? "cursor-pointer hover:brightness-[0.97]" : "cursor-default"} ${getDueStateRowBg(sub.due_state, sub.workflow_status)}`}>
                    <td className="px-5 py-3">
                      <p className="text-[13px] font-medium text-[#191c1e] max-w-[160px] truncate">{sub.provider_name}</p>
                      <p className="text-[11px] text-[#737780]">
                        {SECTOR_LABELS[sub.provider_sector]} · {PROVIDER_CATEGORY_LABELS[sub.provider_category] ?? sub.provider_category}
                      </p>
                    </td>
                    <td className="px-5 py-3">
                      <p className="text-[12px] font-mono font-medium text-[#002d5b]">{sub.form_code}</p>
                      {sub.submission_reference&&<p className="mt-1 max-w-[240px] break-all font-mono text-[10px] text-[#737780]">{sub.submission_reference}</p>}
                    </td>
                    <td className="px-5 py-3 text-[12px] text-[#43474f]">{sub.period_name}</td>
                    <td className="px-5 py-3 text-[12px] tabular-nums text-[#43474f]">
                      {sub.due_at ? formatDate(sub.due_at) : "—"}
                    </td>
                    <td className="px-5 py-3"><WorkflowBadge status={sub.workflow_status} /></td>
                    <td className="whitespace-nowrap px-5 py-3 text-[12px] text-[#43474f]">
                      {sub.latest_action_at ? formatTransmissionDateTime(sub.latest_action_at) : sub.latest_message?.created_at ? formatTransmissionDateTime(sub.latest_message.created_at) : "—"}
                    </td>
                    <td className="max-w-[260px] px-5 py-3">
                      {sub.latest_message ? <>
                        <p className="truncate text-[12px] font-semibold text-[#191c1e]" title={sub.latest_message.subject}>{sub.latest_message.subject}</p>
                        {sub.latest_message.preview && <p className="mt-0.5 truncate text-[11px] text-[#737780]" title={sub.latest_message.body}>{sub.latest_message.preview}</p>}
                      </> : <span className="text-[12px] text-[#737780]">No communication</span>}
                    </td>
                    <td className="px-5 py-3">{sub.open_compliance_flag_count > 0 ? <span className="inline-flex rounded-full bg-[#fff0c2] px-2.5 py-1 text-[11px] font-semibold text-[#6b4800]">{sub.open_compliance_flag_count} flag{sub.open_compliance_flag_count === 1 ? "" : "s"}</span> : <span className="text-[11px] text-[#737780]">Clear</span>}</td>
                    <td className="px-5 py-3"><DueStateBadge state={sub.due_state} /></td>
                    <td className="px-5 py-3">
                      {sub.latest_submission_id ? <Link href={`/submissions/${sub.latest_submission_id}/review`}
                        onClick={(event) => event.stopPropagation()}
                        className="flex items-center gap-1 text-[12px] font-medium text-[#0066cc] hover:text-[#002d5b] transition-colors">
                        Review <ChevronRight size={12} />
                      </Link> : <span title="No submission version exists for this obligation." className="text-[12px] text-[#737780]">Unavailable</span>}
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table></div>
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

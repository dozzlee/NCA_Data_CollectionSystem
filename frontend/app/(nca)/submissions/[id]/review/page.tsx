"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime, WORKFLOW_LABELS } from "@/lib/utils";
import {
  CheckCircle2, XCircle, AlertTriangle, MessageSquare,
  Clock, ChevronDown, ChevronUp, ChevronRight,
} from "lucide-react";
import type { WorkflowStatus, FormSection, FieldStatus } from "@/lib/types";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ReviewAction {
  id: number; action: string; target_type: string; target_id: string;
  comment: string; is_provider_visible: boolean;
  created_by: number; created_by_name: string; created_at: string;
}

interface Submission {
  id: number; version: number; completion_pct: string;
  workflow_status: WorkflowStatus; form_code: string; form_name: string;
  period_name: string; provider_name: string;
  submitted_at: string | null; reviewed_at: string | null; kmz_required: boolean;
}

interface SectionValue {
  id: number; field: number | null; grid: number | null;
  grid_row_id: string; grid_column: number | null;
  value: string; value_status: FieldStatus; explanation: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const ACTION_ICONS: Record<string, React.ElementType> = {
  APPROVE: CheckCircle2, REJECT: XCircle,
  REQUEST_CORRECTION: AlertTriangle,
  ADD_NOTE: MessageSquare, ADD_PROVIDER_COMMENT: MessageSquare,
};
const ACTION_COLORS: Record<string, string> = {
  APPROVE: "text-[#1f7a4d]", REJECT: "text-[#e31937]",
  REQUEST_CORRECTION: "text-[#7a5c00]",
  ADD_NOTE: "text-[#0066cc]", ADD_PROVIDER_COMMENT: "text-[#275fa5]",
};

const STATUS_LABELS: Partial<Record<FieldStatus, string>> = {
  NOT_APPLICABLE:        "N/A",
  NOT_AVAILABLE:         "Not Available",
  NOT_REQUIRED:          "Not Required",
  PENDING_CLARIFICATION: "Pending Clarification",
  WAITING_CORRECTION:    "Needs Correction",
  SYSTEM_CALCULATED:     "Auto-calculated",
};

const STATUS_COLORS: Partial<Record<FieldStatus, string>> = {
  PROVIDED:              "text-[#191c1e]",
  NOT_APPLICABLE:        "text-[#737780] italic",
  NOT_AVAILABLE:         "text-[#737780] italic",
  NOT_REQUIRED:          "text-[#737780] italic",
  PENDING_CLARIFICATION: "text-[#7a5c00]",
  WAITING_CORRECTION:    "text-[#c0112a] font-semibold",
  MISSING:               "text-[#c0112a]",
  SYSTEM_CALCULATED:     "text-[#0066cc]",
};

// ─── Section Data Panel ───────────────────────────────────────────────────────

function SectionDataPanel({
  section, submissionId,
}: { section: FormSection; submissionId: number }) {
  const [open, setOpen] = useState(false);

  const { data: values, isLoading } = useQuery<SectionValue[]>({
    queryKey: ["section-values", submissionId, section.section_code],
    queryFn: () => api(`/submissions/${submissionId}/sections/${section.section_code}/values/`),
    enabled: open,
  });

  const valueMap = new Map((values ?? []).map(v => [v.field, v]));

  const hasIssues = (values ?? []).some(v =>
    v.value_status === "MISSING" || v.value_status === "WAITING_CORRECTION"
  );
  const allProvided = section.fields.length > 0 &&
    section.fields.filter(f => f.is_required).every(f => {
      const v = valueMap.get(f.id);
      return v && v.value_status !== "MISSING";
    });

  return (
    <div className={`rounded-[10px] border overflow-hidden ${
      hasIssues ? "border-[#e31937]/30" : allProvided ? "border-[#c3c6d0]" : "border-[#c3c6d0]"
    }`}>
      {/* Section header */}
      <button onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[#f7f9fb] transition-colors">
        <div className={`h-2.5 w-2.5 rounded-full shrink-0 ${
          hasIssues ? "bg-[#e31937]" : allProvided ? "bg-[#1f7a4d]" : "bg-[#c3c6d0]"
        }`} />
        <p className="flex-1 text-[13px] font-semibold text-[#191c1e]">{section.title}</p>
        <span className="text-[11px] text-[#737780] mr-2">
          {section.fields.filter(f => f.is_required).length} required field{section.fields.filter(f => f.is_required).length !== 1 ? "s" : ""}
          {section.grids.length > 0 && ` · ${section.grids.length} table${section.grids.length !== 1 ? "s" : ""}`}
        </span>
        {hasIssues && (
          <span className="mr-2 rounded-full bg-[#ffe8e8] px-2 py-0.5 text-[10px] font-bold text-[#c0112a]">Issues</span>
        )}
        {open ? <ChevronUp size={14} className="text-[#737780] shrink-0" /> : <ChevronRight size={14} className="text-[#737780] shrink-0" />}
      </button>

      {/* Section values */}
      {open && (
        <div className="border-t border-[#eceef0] bg-white">
          {isLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          ) : section.fields.length === 0 && section.grids.length === 0 ? (
            <p className="px-4 py-3 text-[12px] text-[#737780]">No fields in this section.</p>
          ) : (
            <div>
              {/* Scalar fields */}
              {section.fields.length > 0 && (
                <table className="w-full text-left">
                  <thead className="bg-[#f7f9fb] border-b border-[#eceef0]">
                    <tr>
                      <th className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-[#737780] w-1/2">Field</th>
                      <th className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-[#737780]">Value</th>
                      <th className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-[#737780] w-24">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#f2f4f6]">
                    {section.fields.map(field => {
                      const v = valueMap.get(field.id);
                      const status = v?.value_status ?? "MISSING";
                      const displayValue = v?.value || STATUS_LABELS[status as FieldStatus] || "—";
                      const isIssue = status === "MISSING" || status === "WAITING_CORRECTION";
                      return (
                        <tr key={field.id} className={isIssue ? "bg-[#fff8f8]" : ""}>
                          <td className="px-4 py-2.5">
                            <p className="text-[12px] text-[#43474f]">{field.label}</p>
                            {field.unit && <p className="text-[10px] text-[#737780]">{field.unit}</p>}
                            {!field.is_required && (
                              <span className="text-[10px] text-[#737780]">Optional</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            <p className={`text-[13px] font-medium ${STATUS_COLORS[status as FieldStatus] ?? "text-[#191c1e]"}`}>
                              {status === "PROVIDED" || status === "SYSTEM_CALCULATED"
                                ? (displayValue || "—")
                                : <span className="italic">{STATUS_LABELS[status as FieldStatus] ?? displayValue}</span>
                              }
                            </p>
                            {v?.explanation && (
                              <p className="text-[11px] text-[#737780] mt-0.5 italic">{v.explanation}</p>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            {isIssue && (
                              <span className="text-[10px] font-bold text-[#c0112a]">
                                {status === "WAITING_CORRECTION" ? "⚑ Fix needed" : "⚑ Missing"}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
              {/* Note for grids */}
              {section.grids.length > 0 && (
                <div className="px-4 py-3 border-t border-[#eceef0] bg-[#f7f9fb]">
                  <p className="text-[11px] text-[#737780]">
                    This section also contains {section.grids.length} table{section.grids.length !== 1 ? "s" : ""} —
                    grid data is stored at field level. Review the individual values above.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Review Page ─────────────────────────────────────────────────────────

export default function ReviewPage() {
  const params = useParams();
  const submissionId = Number(params.id);
  const qc = useQueryClient();

  const [comment, setComment]           = useState("");
  const [action, setAction]             = useState<"approve" | "reject" | "correction" | "note" | null>(null);
  const [showHistory, setShowHistory]   = useState(true);
  const [activeTab, setActiveTab]       = useState<"data" | "review">("data");
  const [submitting, setSubmitting]     = useState(false);
  const [error, setError]               = useState<string | null>(null);

  const submissionQ = useQuery({
    queryKey: ["submission", submissionId],
    queryFn: () => api.get<Submission>(`/submissions/${submissionId}/`),
  });

  const historyQ = useQuery({
    queryKey: ["review-history", submissionId],
    queryFn: () => api.get<ReviewAction[]>(`/submissions/${submissionId}/review/history/`),
  });

  const completionQ = useQuery({
    queryKey: ["submission-completion", submissionId],
    queryFn: () => api.get<{
      completion_pct: number;
      sections: { section_code: string; title: string; required: number; provided: number; complete: boolean }[]
    }>(`/submissions/${submissionId}/completion/`),
  });

  // Fetch the full form template to get sections + fields for the data viewer
  const sub = submissionQ.data;
  const formTemplateQ = useQuery({
    queryKey: ["form-template-for-review", sub?.form_code],
    queryFn: () => api.get<{ results: { id: number; form_code: string }[] }>(`/form-templates/?form_code=${sub?.form_code}`).then(d => {
      const tmpl = (d as unknown as { results: { id: number }[] }).results?.[0];
      if (!tmpl) return null;
      return api.get<{ sections: FormSection[] }>(`/form-templates/${tmpl.id}/`);
    }),
    enabled: !!sub?.form_code,
  });

  const completion = completionQ.data;
  const formSections: FormSection[] = (formTemplateQ.data as { sections: FormSection[] } | null)?.sections ?? [];

  async function submitAction() {
    if (!action) return;
    if (action !== "approve" && !comment.trim()) { setError("Comment is required."); return; }
    setSubmitting(true); setError(null);
    try {
      const endpoints: Record<string, string> = {
        approve:    `/submissions/${submissionId}/review/approve/`,
        reject:     `/submissions/${submissionId}/review/reject/`,
        correction: `/submissions/${submissionId}/review/request-correction/`,
        note:       `/submissions/${submissionId}/review/add-note/`,
      };
      await api.post(endpoints[action], { comment, targets: [] });
      setComment(""); setAction(null);
      qc.invalidateQueries({ queryKey: ["submission", submissionId] });
      qc.invalidateQueries({ queryKey: ["review-history", submissionId] });
    } catch {
      setError("Action failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submissionQ.isLoading) {
    return <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}</div>;
  }
  if (!sub) return <p className="text-[13px] text-[#737780]">Submission not found.</p>;

  const reviewable = ["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED"].includes(sub.workflow_status);
  const missingCount = (completion?.sections ?? []).filter(s => !s.complete).length;

  return (
    <div className="space-y-5 max-w-[1080px]">
      {/* Back nav */}
      <a href="/submissions"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
        ← Back to Submissions
      </a>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{sub.form_code}</p>
            <WorkflowBadge status={sub.workflow_status} />
            {missingCount > 0 && (
              <span className="rounded-full bg-[#ffe8e8] px-2.5 py-0.5 text-[11px] font-semibold text-[#c0112a]">
                {missingCount} incomplete section{missingCount !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <h1 className="text-[20px] font-semibold text-[#191c1e]">{sub.form_name}</h1>
          <p className="text-[13px] text-[#737780] mt-0.5">{sub.provider_name} · {sub.period_name}</p>
        </div>
        <div className="text-right shrink-0 space-y-1">
          {sub.submitted_at && (
            <div>
              <p className="text-[11px] text-[#737780]">Submitted</p>
              <p className="text-[12px] font-medium text-[#43474f]">{formatDateTime(sub.submitted_at)}</p>
            </div>
          )}
          <div>
            <p className="text-[11px] text-[#737780]">Completion</p>
            <p className="text-[14px] font-bold text-[#0066cc]">{Number(sub.completion_pct).toFixed(0)}%</p>
          </div>
        </div>
      </div>

      {/* Completion bar */}
      <div className="h-2 w-full rounded-full bg-[#eceef0] overflow-hidden">
        <div className="h-full rounded-full transition-all"
          style={{
            width: `${sub.completion_pct}%`,
            background: Number(sub.completion_pct) < 50
              ? "#e31937" : Number(sub.completion_pct) < 80
              ? "#ffd100" : "#1f7a4d"
          }} />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#eceef0]">
        {([["data","Form Data"], ["review","Review & Actions"]] as const).map(([t, label]) => (
          <button key={t} onClick={() => setActiveTab(t)}
            className={`px-5 py-3 text-[13px] font-medium border-b-2 transition-colors ${
              activeTab === t
                ? "border-[#001836] text-[#191c1e]"
                : "border-transparent text-[#737780] hover:text-[#43474f]"
            }`}>
            {label}
            {t === "review" && historyQ.data && historyQ.data.length > 0 && (
              <span className="ml-1.5 rounded-full bg-[#f2f4f6] px-1.5 py-0.5 text-[10px] font-bold text-[#43474f]">
                {historyQ.data.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab: Form Data ─────────────────────────────────────────── */}
      {activeTab === "data" && (
        <div className="grid grid-cols-4 gap-5">
          {/* Section map — left sidebar */}
          <div className="col-span-1">
            <div className="rounded-[12px] border border-[#eceef0] bg-white p-4 sticky top-4">
              <p className="text-[12px] font-semibold text-[#191c1e] mb-3">Sections</p>
              <div className="space-y-1">
                {(completion?.sections ?? []).map(s => (
                  <div key={s.section_code} className="flex items-center gap-2 py-1">
                    <div className={`h-2 w-2 rounded-full shrink-0 ${
                      s.complete ? "bg-[#1f7a4d]" : s.provided > 0 ? "bg-[#ffd100]" : "bg-[#c3c6d0]"
                    }`} />
                    <p className="text-[11px] text-[#43474f] flex-1 leading-tight">{s.title}</p>
                    <p className="text-[10px] tabular-nums text-[#737780] shrink-0">{s.provided}/{s.required}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Section data — main panel */}
          <div className="col-span-3 space-y-3">
            {formTemplateQ.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-[10px]" />)
            ) : formSections.length === 0 ? (
              <div className="rounded-[12px] border border-[#eceef0] bg-white p-8 text-center">
                <p className="text-[14px] text-[#737780]">Form data unavailable.</p>
                <p className="text-[12px] text-[#737780] mt-1">The form template could not be loaded.</p>
              </div>
            ) : (
              formSections.map(section => (
                <SectionDataPanel key={section.id} section={section} submissionId={submissionId} />
              ))
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Review & Actions ───────────────────────────────────── */}
      {activeTab === "review" && (
        <div className="grid grid-cols-3 gap-5">
          {/* Left: completion + details */}
          <div className="col-span-1 space-y-4">
            <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-4">
              <p className="text-[13px] font-semibold text-[#191c1e] mb-3">Section completion</p>
              <div className="space-y-1">
                {completion?.sections.map(s => (
                  <div key={s.section_code} className="flex items-center gap-2 py-1 border-b border-[#f2f4f6] last:border-0">
                    <div className={`h-2 w-2 rounded-full shrink-0 ${
                      s.complete ? "bg-[#1f7a4d]" : s.provided > 0 ? "bg-[#ffd100]" : "bg-[#c3c6d0]"
                    }`} />
                    <p className="text-[11px] text-[#43474f] flex-1 truncate">{s.title}</p>
                    <p className="text-[10px] tabular-nums text-[#737780] shrink-0">{s.provided}/{s.required}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-4 space-y-2">
              <p className="text-[12px] font-semibold text-[#191c1e] mb-2">Details</p>
              {[
                { label:"Version",       value:`v${sub.version}` },
                { label:"Form",          value:sub.form_code },
                { label:"Period",        value:sub.period_name },
                { label:"KMZ required",  value:sub.kmz_required ? "Yes (fibre)" : "No" },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between">
                  <p className="text-[11px] text-[#737780]">{label}</p>
                  <p className="text-[11px] font-medium text-[#43474f]">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Right: action panel + history */}
          <div className="col-span-2 space-y-4">
            {reviewable && (
              <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-5">
                <p className="text-[13px] font-semibold text-[#191c1e] mb-4">Review Action</p>
                <div className="grid grid-cols-2 gap-2 mb-4">
                  {([
                    { key:"approve",    label:"Approve",            icon:CheckCircle2, color:"border-[#1f7a4d] text-[#1f7a4d] hover:bg-[#e5f4eb]" },
                    { key:"reject",     label:"Reject",             icon:XCircle,      color:"border-[#e31937] text-[#e31937] hover:bg-[#ffe8e8]" },
                    { key:"correction", label:"Request Correction",  icon:AlertTriangle,color:"border-[#ffd100] text-[#7a5c00] hover:bg-[#fff3bf]" },
                    { key:"note",       label:"Add Internal Note",   icon:MessageSquare,color:"border-[#c3c6d0] text-[#43474f] hover:bg-[#f2f4f6]" },
                  ] as const).map(({ key, label, icon: Icon, color }) => (
                    <button key={key} onClick={() => setAction(action === key ? null : key)}
                      className={`flex items-center gap-2 rounded-[8px] border px-3 py-2.5 text-[12px] font-medium transition-colors ${color} ${action === key ? "ring-2 ring-current ring-offset-1" : ""}`}>
                      <Icon size={14} /> {label}
                    </button>
                  ))}
                </div>
                {action && (
                  <div className="space-y-3">
                    <textarea value={comment} onChange={e => setComment(e.target.value)} rows={3}
                      placeholder={
                        action === "approve"    ? "Optional comment for the record…"
                        : action === "reject"   ? "State the reason for rejection…"
                        : action === "correction" ? "Describe what needs to be corrected…"
                        : "Internal note (not visible to provider)…"
                      }
                      className="w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] placeholder:text-[#737780] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20 resize-none" />
                    {error && <p className="text-[12px] text-[#e31937]">{error}</p>}
                    <div className="flex gap-2">
                      <button onClick={submitAction} disabled={submitting}
                        className="rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#001836] disabled:opacity-60 transition-colors">
                        {submitting ? "Submitting…" : "Confirm"}
                      </button>
                      <button onClick={() => { setAction(null); setComment(""); setError(null); }}
                        className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[12px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Review history */}
            <div className="rounded-[16px] bg-white border border-[#e6e8ea]">
              <button onClick={() => setShowHistory(h => !h)}
                className="flex w-full items-center justify-between px-5 py-4 border-b border-[#eceef0]">
                <p className="text-[13px] font-semibold text-[#191c1e]">Review History</p>
                {showHistory ? <ChevronUp size={14} className="text-[#737780]" /> : <ChevronDown size={14} className="text-[#737780]" />}
              </button>
              {showHistory && (
                <div className="px-5 py-3 divide-y divide-[#f2f4f6]">
                  {historyQ.isLoading
                    ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="my-3 h-12 w-full" />)
                    : !historyQ.data?.length
                    ? <p className="py-6 text-center text-[13px] text-[#737780]">No review actions yet.</p>
                    : historyQ.data.map(item => {
                        const Icon = ACTION_ICONS[item.action] ?? Clock;
                        const color = ACTION_COLORS[item.action] ?? "text-[#43474f]";
                        return (
                          <div key={item.id} className="flex gap-3 py-3">
                            <Icon size={15} className={`shrink-0 mt-0.5 ${color}`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-baseline gap-2 flex-wrap">
                                <p className={`text-[12px] font-semibold ${color}`}>
                                  {item.action.replace(/_/g, " ")}
                                </p>
                                <p className="text-[11px] text-[#737780]">by {item.created_by_name}</p>
                                <p className="text-[11px] text-[#737780] ml-auto tabular-nums">
                                  {formatDateTime(item.created_at)}
                                </p>
                              </div>
                              {item.comment && <p className="mt-1 text-[12px] text-[#43474f] leading-snug">{item.comment}</p>}
                              {item.is_provider_visible && (
                                <span className="mt-1 inline-block text-[10px] font-medium text-[#275fa5] bg-[#e8f0fe] rounded-full px-2 py-0.5">
                                  Visible to provider
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })
                  }
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

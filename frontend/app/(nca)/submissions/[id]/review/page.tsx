"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime, WORKFLOW_LABELS } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertTriangle, MessageSquare, Clock, ChevronDown, ChevronUp } from "lucide-react";
import type { WorkflowStatus } from "@/lib/types";

interface ReviewAction {
  id: number;
  action: string;
  target_type: string;
  target_id: string;
  comment: string;
  is_provider_visible: boolean;
  created_by: number;
  created_by_name: string;
  created_at: string;
}

interface Submission {
  id: number;
  version: number;
  completion_pct: string;
  workflow_status: WorkflowStatus;
  form_code: string;
  form_name: string;
  period_name: string;
  provider_name: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  kmz_required: boolean;
}

const ACTION_ICONS: Record<string, React.ElementType> = {
  APPROVE: CheckCircle2,
  REJECT: XCircle,
  REQUEST_CORRECTION: AlertTriangle,
  ADD_NOTE: MessageSquare,
  ADD_PROVIDER_COMMENT: MessageSquare,
};

const ACTION_COLORS: Record<string, string> = {
  APPROVE: "text-[#1f7a4d]",
  REJECT: "text-[#E31937]",
  REQUEST_CORRECTION: "text-[#7a5c00]",
  ADD_NOTE: "text-[#0066cc]",
  ADD_PROVIDER_COMMENT: "text-[#275fa5]",
};

export default function ReviewPage() {
  const params = useParams();
  const submissionId = Number(params.id);
  const qc = useQueryClient();

  const [comment, setComment] = useState("");
  const [action, setAction] = useState<"approve" | "reject" | "correction" | "note" | null>(null);
  const [showHistory, setShowHistory] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    queryFn: () => api.get<{ completion_pct: number; sections: { section_code: string; title: string; required: number; provided: number; complete: boolean }[] }>(`/submissions/${submissionId}/completion/`),
  });

  const sub = submissionQ.data;
  const completion = completionQ.data;

  async function submitAction() {
    if (!action || !comment.trim()) { setError("Comment is required."); return; }
    setSubmitting(true);
    setError(null);
    try {
      const endpoints: Record<string, string> = {
        approve: `/submissions/${submissionId}/review/approve/`,
        reject: `/submissions/${submissionId}/review/reject/`,
        correction: `/submissions/${submissionId}/review/request-correction/`,
        note: `/submissions/${submissionId}/review/add-note/`,
      };
      await api.post(endpoints[action], { comment, targets: [] });
      setComment("");
      setAction(null);
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

  return (
    <div className="space-y-5 max-w-[960px]">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{sub.form_code}</p>
            <WorkflowBadge status={sub.workflow_status} />
          </div>
          <h1 className="text-[20px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>{sub.form_name}</h1>
          <p className="text-[13px] text-[#737780] mt-0.5">{sub.provider_name} · {sub.period_name}</p>
        </div>
        {sub.submitted_at && (
          <div className="text-right shrink-0">
            <p className="text-[11px] text-[#737780]">Submitted</p>
            <p className="text-[12px] font-medium text-[#43474f]">{formatDateTime(sub.submitted_at)}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Left: section completion */}
        <div className="col-span-1 space-y-3">
          <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-4" style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[13px] font-semibold text-[#191c1e]">Completion</p>
              <p className="text-[13px] font-semibold text-[#0066cc] tabular-nums">{Number(sub.completion_pct).toFixed(0)}%</p>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[#eceef0] overflow-hidden mb-4">
              <div className="h-full rounded-full bg-[#0066cc] transition-all" style={{ width: `${sub.completion_pct}%` }} />
            </div>
            {completion?.sections.map((s) => (
              <div key={s.section_code} className="flex items-center gap-2 py-1.5 border-b border-[#f2f4f6] last:border-0">
                <div className={`h-2 w-2 rounded-full shrink-0 ${s.complete ? "bg-[#1f7a4d]" : s.provided > 0 ? "bg-[#ffd100]" : "bg-[#c3c6d0]"}`} />
                <p className="text-[11px] text-[#43474f] flex-1 truncate">{s.title}</p>
                <p className="text-[10px] tabular-nums text-[#737780] shrink-0">{s.provided}/{s.required}</p>
              </div>
            ))}
          </div>

          {/* Submission meta */}
          <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-4 space-y-2" style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
            <p className="text-[12px] font-semibold text-[#191c1e] mb-2">Details</p>
            {[
              { label: "Version", value: `v${sub.version}` },
              { label: "Form", value: sub.form_code },
              { label: "Period", value: sub.period_name },
              { label: "KMZ required", value: sub.kmz_required ? "Yes (fibre)" : "No" },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between">
                <p className="text-[11px] text-[#737780]">{label}</p>
                <p className="text-[11px] font-medium text-[#43474f]">{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right: review actions + history */}
        <div className="col-span-2 space-y-4">

          {/* Action panel */}
          {reviewable && (
            <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-5" style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
              <p className="text-[13px] font-semibold text-[#191c1e] mb-4">Review Action</p>

              {/* Action buttons */}
              <div className="grid grid-cols-2 gap-2 mb-4">
                {([
                  { key: "approve", label: "Approve", icon: CheckCircle2, color: "border-[#1f7a4d] text-[#1f7a4d] hover:bg-[#e5f4eb]" },
                  { key: "reject", label: "Reject", icon: XCircle, color: "border-[#E31937] text-[#E31937] hover:bg-[#ffe8e8]" },
                  { key: "correction", label: "Request Correction", icon: AlertTriangle, color: "border-[#ffd100] text-[#7a5c00] hover:bg-[#fff3bf]" },
                  { key: "note", label: "Add Note", icon: MessageSquare, color: "border-[#c3c6d0] text-[#43474f] hover:bg-[#f2f4f6]" },
                ] as const).map(({ key, label, icon: Icon, color }) => (
                  <button
                    key={key}
                    onClick={() => setAction(action === key ? null : key)}
                    className={`flex items-center gap-2 rounded-[8px] border px-3 py-2.5 text-[12px] font-medium transition-colors ${color} ${action === key ? "ring-2 ring-current ring-offset-1" : ""}`}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}
              </div>

              {action && (
                <div className="space-y-3">
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                    placeholder={
                      action === "approve" ? "Optional comment for the record…"
                      : action === "reject" ? "State the reason for rejection…"
                      : action === "correction" ? "Describe what needs to be corrected…"
                      : "Internal note (not visible to provider)…"
                    }
                    className="w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20 resize-none"
                  />
                  {error && <p className="text-[12px] text-[#E31937]">{error}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={submitAction}
                      disabled={submitting}
                      className="rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#001836] disabled:opacity-60 transition-colors"
                    >
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
          <div className="rounded-[16px] bg-white border border-[#e6e8ea]" style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
            <button
              onClick={() => setShowHistory((h) => !h)}
              className="flex w-full items-center justify-between px-5 py-4 border-b border-[#eceef0]"
            >
              <p className="text-[13px] font-semibold text-[#191c1e]">Review History</p>
              {showHistory ? <ChevronUp size={14} className="text-[#737780]" /> : <ChevronDown size={14} className="text-[#737780]" />}
            </button>

            {showHistory && (
              <div className="px-5 py-3 space-y-0 divide-y divide-[#f2f4f6]">
                {historyQ.isLoading ? (
                  Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="my-3 h-12 w-full" />)
                ) : !historyQ.data?.length ? (
                  <p className="py-6 text-center text-[13px] text-[#737780]">No review actions yet.</p>
                ) : (
                  historyQ.data.map((item) => {
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
                            <p className="text-[11px] text-[#737780] ml-auto tabular-nums">{formatDateTime(item.created_at)}</p>
                          </div>
                          {item.comment && <p className="mt-1 text-[12px] text-[#43474f] leading-snug">{item.comment}</p>}
                          {item.is_provider_visible && (
                            <span className="mt-1 inline-block text-[10px] font-medium text-[#275fa5] bg-[#e8f0fe] rounded-full px-2 py-0.5">Visible to provider</span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate, formatDateTime } from "@/lib/utils";
import { AlertTriangle, Mail, Send, CheckCircle2, Clock } from "lucide-react";
import type { ExpectedSubmission } from "@/lib/types";
import type { PaginatedResponse } from "@/lib/types";

interface ComplianceSummary {
  overdue: number;
  correction_requested: number;
  not_started_open: number;
  draft_due_soon: number;
  pending_email_drafts: number;
  total_requiring_action: number;
}

interface EmailLog {
  id: number;
  subject: string;
  provider_name: string;
  compliance_stage: string;
  status: "DRAFT" | "SENT" | "FAILED";
  generated_by_name: string;
  generated_at: string;
  sent_at: string | null;
}

interface EmailTemplate {
  id: number;
  template_type: string;
  subject: string;
}

const TEMPLATE_LABELS: Record<string, string> = {
  PERIOD_OPEN: "Period Opening Notice",
  REMINDER: "Submission Reminder",
  OVERDUE: "Overdue Notice",
  CORRECTION_REQUEST: "Correction Request",
  DRAFT_INCOMPLETE: "Draft Incomplete",
  ESCALATION: "Escalation Notice",
};

export default function CompliancePage() {
  const qc = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [templateType, setTemplateType] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<string | null>(null);

  const summaryQ = useQuery({
    queryKey: ["compliance-summary"],
    queryFn: () => api.get<ComplianceSummary>("/compliance/"),
  });

  const overdueQ = useQuery({
    queryKey: ["expected-overdue"],
    queryFn: () => api.get<PaginatedResponse<ExpectedSubmission>>("/expected-submissions/?due_state=OVERDUE"),
  });

  const emailsQ = useQuery({
    queryKey: ["email-logs"],
    queryFn: () => api.get<EmailLog[]>("/compliance/emails/"),
  });

  const templatesQ = useQuery({
    queryKey: ["email-templates"],
    queryFn: () => api.get<EmailTemplate[]>("/compliance/email-templates/"),
  });

  async function handleGenerateEmails() {
    if (!templateType || !selectedIds.length) return;
    setGenerating(true);
    setGenResult(null);
    try {
      const res = await api.post<{ generated: number }>("/compliance/generate-email/", {
        template_type: templateType,
        expected_submission_ids: selectedIds,
      }) as { generated: number };
      setGenResult(`${res.generated} email draft(s) generated.`);
      setSelectedIds([]);
      qc.invalidateQueries({ queryKey: ["email-logs"] });
      qc.invalidateQueries({ queryKey: ["compliance-summary"] });
    } catch {
      setGenResult("Failed to generate emails.");
    } finally {
      setGenerating(false);
    }
  }

  async function markSent(emailId: number) {
    await api.patch(`/compliance/emails/${emailId}/mark-sent/`, {});
    qc.invalidateQueries({ queryKey: ["email-logs"] });
    qc.invalidateQueries({ queryKey: ["compliance-summary"] });
  }

  const s = summaryQ.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Compliance</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">Monitor non-compliance and send follow-up notices</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Overdue", value: s?.overdue ?? 0, icon: AlertTriangle, color: "#E31937" },
          { label: "Correction Requested", value: s?.correction_requested ?? 0, icon: AlertTriangle, color: "#ffd100" },
          { label: "Not Started (Open)", value: s?.not_started_open ?? 0, icon: Clock, color: "#0066cc" },
          { label: "Email Drafts Pending", value: s?.pending_email_drafts ?? 0, icon: Mail, color: "#275fa5" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-[16px] bg-white border border-[#e6e8ea] p-5"
            style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{label}</p>
              <div className="h-8 w-8 flex items-center justify-center rounded-[8px]" style={{ background: color + "18" }}>
                <Icon size={14} style={{ color }} />
              </div>
            </div>
            {summaryQ.isLoading
              ? <Skeleton className="h-8 w-12" />
              : <p className="text-[28px] font-semibold tabular-nums text-[#191c1e]" style={{ letterSpacing: "-0.02em" }}>{value}</p>
            }
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Overdue list + bulk email */}
        <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#eceef0]">
            <p className="text-[13px] font-semibold text-[#191c1e]">Overdue Submissions</p>
            {selectedIds.length > 0 && (
              <span className="text-[11px] font-medium text-[#0066cc]">{selectedIds.length} selected</span>
            )}
          </div>

          <div className="divide-y divide-[#f2f4f6] max-h-[340px] overflow-y-auto">
            {overdueQ.isLoading
              ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="px-5 py-3"><Skeleton className="h-10 w-full" /></div>)
              : !overdueQ.data?.results.length
              ? <p className="px-5 py-8 text-center text-[13px] text-[#737780]">No overdue submissions.</p>
              : overdueQ.data.results.map((sub) => {
                  const checked = selectedIds.includes(sub.id);
                  return (
                    <label key={sub.id} className="flex items-center gap-3 px-5 py-3 hover:bg-[#f7f9fb] cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => setSelectedIds((ids) => e.target.checked ? [...ids, sub.id] : ids.filter((i) => i !== sub.id))}
                        className="h-4 w-4 accent-[#0066cc]"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-[12px] font-medium text-[#191c1e] truncate">{sub.provider_name}</p>
                        <p className="text-[11px] text-[#737780]">{sub.form_code} · {sub.period_name}</p>
                      </div>
                      <DueStateBadge state={sub.due_state} />
                    </label>
                  );
                })
            }
          </div>

          {/* Generate email section */}
          <div className="border-t border-[#eceef0] px-5 py-4 space-y-3">
            <div className="flex gap-2">
              <select
                value={templateType}
                onChange={(e) => setTemplateType(e.target.value)}
                className="flex-1 rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[12px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]"
              >
                <option value="">Select email template…</option>
                {(templatesQ.data ?? []).map((t) => (
                  <option key={t.id} value={t.template_type}>
                    {TEMPLATE_LABELS[t.template_type] ?? t.template_type}
                  </option>
                ))}
              </select>
              <button
                onClick={handleGenerateEmails}
                disabled={!templateType || !selectedIds.length || generating}
                className="flex items-center gap-1.5 rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#001836] disabled:opacity-40 transition-colors shrink-0"
              >
                <Mail size={12} />
                {generating ? "Generating…" : "Generate drafts"}
              </button>
            </div>
            {genResult && <p className="text-[11px] font-medium text-[#1f7a4d]">{genResult}</p>}
            <p className="text-[10px] text-[#737780]">Select submissions above, pick a template, and generate email drafts. Mark as sent after dispatching manually.</p>
          </div>
        </div>

        {/* Email log */}
        <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
          <div className="px-5 py-4 border-b border-[#eceef0]">
            <p className="text-[13px] font-semibold text-[#191c1e]">Email Log</p>
          </div>
          <div className="divide-y divide-[#f2f4f6] max-h-[420px] overflow-y-auto">
            {emailsQ.isLoading
              ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="px-5 py-3"><Skeleton className="h-12 w-full" /></div>)
              : !emailsQ.data?.length
              ? <p className="px-5 py-8 text-center text-[13px] text-[#737780]">No emails generated yet.</p>
              : emailsQ.data.map((email) => (
                  <div key={email.id} className="flex items-start gap-3 px-5 py-3">
                    <div className={`mt-0.5 h-2 w-2 rounded-full shrink-0 ${email.status === "SENT" ? "bg-[#1f7a4d]" : email.status === "DRAFT" ? "bg-[#ffd100]" : "bg-[#E31937]"}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-[#191c1e] truncate">{email.subject}</p>
                      <p className="text-[11px] text-[#737780]">{email.provider_name} · {TEMPLATE_LABELS[email.compliance_stage] ?? email.compliance_stage}</p>
                      <p className="text-[10px] text-[#737780] tabular-nums">{formatDateTime(email.generated_at)}</p>
                    </div>
                    {email.status === "DRAFT" && (
                      <button
                        onClick={() => markSent(email.id)}
                        className="flex items-center gap-1 shrink-0 rounded-[6px] border border-[#1f7a4d] px-2 py-1 text-[10px] font-semibold text-[#1f7a4d] hover:bg-[#e5f4eb] transition-colors"
                      >
                        <Send size={9} /> Mark sent
                      </button>
                    )}
                    {email.status === "SENT" && (
                      <span className="flex items-center gap-1 text-[10px] font-medium text-[#1f7a4d] shrink-0">
                        <CheckCircle2 size={11} /> Sent
                      </span>
                    )}
                  </div>
                ))
            }
          </div>
        </div>
      </div>
    </div>
  );
}

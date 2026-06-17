"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime } from "@/lib/utils";
import { AlertTriangle, Mail, Send, CheckCircle2, Clock, ShieldAlert, ChevronRight, ChevronDown, X } from "lucide-react";
import Link from "next/link";
import type { ExpectedSubmission, PaginatedResponse } from "@/lib/types";

interface ComplianceSummary {
  overdue: number;
  correction_requested: number;
  not_started_open: number;
  draft_due_soon: number;
  pending_email_drafts: number;
  total_requiring_action: number;
}

interface ComplianceFlag {
  id: number;
  expected_submission: number;
  provider: number;
  provider_name: string;
  form_code: string;
  period_name: string;
  flag_type: string;
  description: string;
  missing_field_count: number;
  completion_percentage: number;
  status: "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "RESOLVED";
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
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

interface Correspondence {
  id: number;
  flag: number;
  message_type: "NOTE" | "EMAIL_SENT" | "EMAIL_RECEIVED";
  message_type_display: string;
  subject: string;
  message: string;
  created_by_name: string;
  created_at: string;
}

const FLAG_TYPE_LABELS: Record<string, string> = {
  MISSING_DATA: "Missing Data",
  OVERDUE: "Overdue",
  INCOMPLETE: "Incomplete",
  CORRECTION: "Correction",
};

const FLAG_STATUS_STYLES: Record<string, string> = {
  OPEN: "bg-[#ffe8e8] text-[#c0112a]",
  ACKNOWLEDGED: "bg-[#fff3bf] text-[#7a5c00]",
  IN_PROGRESS: "bg-[#e8f1fb] text-[#004999]",
  RESOLVED: "bg-[#e5f4eb] text-[#1f7a4d]",
};

const TEMPLATE_LABELS: Record<string, string> = {
  PERIOD_OPEN: "Period Opening Notice",
  REMINDER: "Submission Reminder",
  OVERDUE: "Overdue Notice",
  CORRECTION_REQUEST: "Correction Request",
  DRAFT_INCOMPLETE: "Draft Incomplete",
  MISSING_FIELDS: "Missing Fields Notice",
  ESCALATION: "Escalation Notice",
};

export default function CompliancePage() {
  const qc = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [templateType, setTemplateType] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<string | null>(null);
  const [flagFilter, setFlagFilter] = useState<string>("OPEN");
  const [expandedFlag, setExpandedFlag] = useState<number | null>(null);
  const [draftingFlag, setDraftingFlag] = useState<number | null>(null);
  const [draftTemplate, setDraftTemplate] = useState("");
  const [noteText, setNoteText] = useState("");
  const [addingNote, setAddingNote] = useState<number | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────
  const summaryQ = useQuery({
    queryKey: ["compliance-summary"],
    queryFn: () => api.get<ComplianceSummary>("/compliance/"),
  });

  const flagsQ = useQuery({
    queryKey: ["compliance-flags", flagFilter],
    queryFn: () => api.get<PaginatedResponse<ComplianceFlag>>(
      `/compliance/flags/${flagFilter ? `?status=${flagFilter}` : ""}`
    ),
  });

  const overdueQ = useQuery({
    queryKey: ["expected-overdue"],
    queryFn: () => api.get<PaginatedResponse<ExpectedSubmission>>("/expected-submissions/?due_state=OVERDUE"),
  });

  const emailsQ = useQuery({
    queryKey: ["email-logs"],
    queryFn: () => api.get<PaginatedResponse<EmailLog>>("/compliance/emails/"),
  });

  const templatesQ = useQuery({
    queryKey: ["email-templates"],
    queryFn: () => api.get<PaginatedResponse<EmailTemplate>>("/compliance/email-templates/"),
  });

  const correspondenceQ = useQuery({
    queryKey: ["flag-correspondence", expandedFlag],
    queryFn: () => expandedFlag ? api.get<PaginatedResponse<Correspondence>>(`/compliance/flags/${expandedFlag}/correspondence/`) : Promise.resolve({ count: 0, results: [] } as unknown as PaginatedResponse<Correspondence>),
    enabled: !!expandedFlag,
  });

  // ── Mutations ─────────────────────────────────────────────────────────────
  const updateStatusMut = useMutation({
    mutationFn: (data: { id: number; status: string }) =>
      api.patch(`/compliance/flags/${data.id}/status/`, { status: data.status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compliance-flags"] });
      qc.invalidateQueries({ queryKey: ["compliance-summary"] });
    },
  });

  const draftEmailMut = useMutation({
    mutationFn: (data: { flag_id: number; template_type: string }) =>
      api.post(`/compliance/flags/${data.flag_id}/draft-email/`, { template_type: data.template_type }),
    onSuccess: () => {
      setDraftingFlag(null);
      setDraftTemplate("");
      qc.invalidateQueries({ queryKey: ["flag-correspondence"] });
      qc.invalidateQueries({ queryKey: ["email-logs"] });
      qc.invalidateQueries({ queryKey: ["compliance-summary"] });
    },
  });

  const addNoteMut = useMutation({
    mutationFn: (data: { flag_id: number; message: string }) =>
      api.post(`/compliance/flags/${data.flag_id}/correspondence/`, {
        message_type: "NOTE",
        message: data.message,
      }),
    onSuccess: () => {
      setAddingNote(null);
      setNoteText("");
      qc.invalidateQueries({ queryKey: ["flag-correspondence"] });
    },
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
      setGenResult("Failed to generate emails. Ensure a template exists for the selected type.");
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
  const flags = flagsQ.data?.results ?? [];
  const overdueList = overdueQ.data?.results ?? [];
  const emails = emailsQ.data?.results ?? [];
  const templates = templatesQ.data?.results ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Compliance</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">Monitor missing data, track flags, and send follow-up notices to providers</p>
      </div>

      {/* ── Summary Cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Overdue", value: s?.overdue ?? 0, icon: AlertTriangle, color: "#E31937" },
          { label: "Correction Requested", value: s?.correction_requested ?? 0, icon: AlertTriangle, color: "#ffd100" },
          { label: "Not Started (Open)", value: s?.not_started_open ?? 0, icon: Clock, color: "#0066cc" },
          { label: "Pending Email Drafts", value: s?.pending_email_drafts ?? 0, icon: Mail, color: "#275fa5" },
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

      {/* ── Compliance Flags (Missing Data) ────────────────────────────────── */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#eceef0]">
          <div className="flex items-center gap-2">
            <ShieldAlert size={15} className="text-[#E31937]" />
            <p className="text-[13px] font-semibold text-[#191c1e]">Missing Data Flags</p>
            {flagsQ.data?.count != null && (
              <span className="rounded-full bg-[#f2f4f6] px-2 py-0.5 text-[11px] font-bold text-[#43474f]">
                {flagsQ.data.count}
              </span>
            )}
          </div>
          <div className="flex gap-1">
            {(["OPEN", "ACKNOWLEDGED", "RESOLVED", ""] as const).map((f) => (
              <button key={f} onClick={() => setFlagFilter(f)}
                className={`rounded-[6px] px-3 py-1 text-[11px] font-semibold transition-colors ${
                  flagFilter === f
                    ? "bg-[#001836] text-white"
                    : "text-[#737780] hover:bg-[#f2f4f6]"
                }`}>
                {f || "All"}
              </button>
            ))}
          </div>
        </div>

        {flagsQ.isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
          </div>
        ) : flags.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <CheckCircle2 size={24} className="mx-auto text-[#1f7a4d] mb-2" />
            <p className="text-[13px] font-medium text-[#191c1e]">No flags in this category</p>
            <p className="text-[12px] text-[#737780] mt-0.5">All submissions are compliant or resolved.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#f2f4f6]">
            {flags.map((flag) => {
              const isExpanded = expandedFlag === flag.id;
              const correspondence = isExpanded ? correspondenceQ.data?.results ?? [] : [];
              return (
                <div key={flag.id} className="border-b border-[#f2f4f6] last:border-b-0">
                  {/* Flag header */}
                  <div className="px-5 py-4 flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <p className="text-[13px] font-semibold text-[#191c1e]">{flag.provider_name}</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${FLAG_STATUS_STYLES[flag.status]}`}>
                          {flag.status}
                        </span>
                        <span className="rounded-full bg-[#f2f4f6] px-2 py-0.5 text-[10px] font-semibold text-[#43474f] uppercase">
                          {FLAG_TYPE_LABELS[flag.flag_type] ?? flag.flag_type}
                        </span>
                      </div>
                      <p className="text-[12px] text-[#43474f]">
                        <span className="font-mono font-medium">{flag.form_code}</span> · {flag.period_name}
                      </p>
                      <p className="text-[11px] text-[#737780] mt-0.5">{flag.description}</p>

                      {/* Completion bar */}
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-[#eceef0] overflow-hidden" style={{ maxWidth: 160 }}>
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${flag.completion_percentage}%`,
                              background: flag.completion_percentage >= 80 ? "#1f7a4d"
                                : flag.completion_percentage >= 40 ? "#ffd100"
                                : "#E31937",
                            }}
                          />
                        </div>
                        <span className="text-[11px] font-semibold text-[#43474f]">
                          {flag.completion_percentage}% complete
                        </span>
                        <span className="text-[11px] text-[#737780]">·</span>
                        <span className="text-[11px] text-[#737780]">{flag.missing_field_count} fields missing</span>
                      </div>
                    </div>

                    {/* Right: actions */}
                    <div className="flex items-start gap-2 shrink-0">
                      <div className="flex flex-col gap-1">
                        <Link href={`/submissions/${flag.expected_submission}/review`}
                          className="rounded-[6px] border border-[#c3c6d0] px-3 py-1.5 text-[11px] font-medium text-[#43474f] hover:bg-[#f2f4f6] flex items-center gap-1 whitespace-nowrap">
                          View <ChevronRight size={11} />
                        </Link>
                        <div className="flex gap-1">
                          {(["OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED"] as const).map((status) => (
                            <button
                              key={status}
                              onClick={() => updateStatusMut.mutate({ id: flag.id, status })}
                              disabled={updateStatusMut.isPending || flag.status === status}
                              className={`rounded-[4px] px-2 py-1 text-[9px] font-semibold whitespace-nowrap transition-colors ${
                                flag.status === status
                                  ? "bg-[#001836] text-white"
                                  : status === "RESOLVED"
                                  ? "border border-[#1f7a4d] text-[#1f7a4d] hover:bg-[#e5f4eb]"
                                  : status === "OPEN"
                                  ? "border border-[#E31937] text-[#E31937] hover:bg-[#ffe8e8]"
                                  : "border border-[#0066cc] text-[#0066cc] hover:bg-[#e8f1fb]"
                              } disabled:opacity-40`}>
                              {status}
                            </button>
                          ))}
                        </div>
                      </div>
                      <button onClick={() => setExpandedFlag(isExpanded ? null : flag.id)}
                        className="text-[#43474f] hover:text-[#191c1e] mt-1">
                        <ChevronDown size={16} style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
                      </button>
                    </div>
                  </div>

                  {/* Correspondence thread (expanded) */}
                  {isExpanded && (
                    <div className="px-5 py-4 bg-[#f7f9fb] border-t border-[#eceef0] space-y-4">
                      {correspondenceQ.isLoading ? (
                        <Skeleton className="h-12 w-full" />
                      ) : correspondence.length === 0 ? (
                        <p className="text-[12px] text-[#737780] italic">No correspondence yet. Start by drafting an email or adding a note.</p>
                      ) : (
                        <div className="space-y-3 max-h-[300px] overflow-y-auto">
                          {correspondence.map((c) => (
                            <div key={c.id} className="rounded-[8px] bg-white border border-[#e6e8ea] p-3">
                              <div className="flex items-start justify-between mb-1">
                                <p className="text-[11px] font-semibold text-[#191c1e]">{c.message_type_display}</p>
                                <p className="text-[10px] text-[#737780]">{formatDateTime(c.created_at)}</p>
                              </div>
                              <p className="text-[10px] text-[#737780] mb-1">by {c.created_by_name}</p>
                              {c.subject && <p className="text-[11px] font-medium text-[#191c1e] mb-1">{c.subject}</p>}
                              <p className="text-[11px] text-[#43474f] whitespace-pre-wrap">{c.message.substring(0, 200)}{c.message.length > 200 ? "…" : ""}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Draft email or add note form */}
                      {draftingFlag === flag.id ? (
                        <div className="rounded-[8px] border border-[#c3c6d0] bg-white p-3 space-y-2">
                          <select value={draftTemplate} onChange={(e) => setDraftTemplate(e.target.value)}
                            className="w-full rounded-[6px] border border-[#c3c6d0] bg-white px-2 py-1.5 text-[11px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
                            <option value="">Select template…</option>
                            {templates.map((t) => (
                              <option key={t.id} value={t.template_type}>
                                {TEMPLATE_LABELS[t.template_type] ?? t.template_type}
                              </option>
                            ))}
                          </select>
                          <div className="flex gap-1.5">
                            <button onClick={() => {
                              if (draftTemplate) {
                                draftEmailMut.mutate({ flag_id: flag.id, template_type: draftTemplate });
                              }
                            }}
                              disabled={!draftTemplate || draftEmailMut.isPending}
                              className="flex-1 rounded-[6px] bg-[#002d5b] px-2 py-1 text-[10px] font-semibold text-white hover:bg-[#001836] disabled:opacity-40">
                              Draft Email
                            </button>
                            <button onClick={() => setDraftingFlag(null)}
                              className="rounded-[6px] border border-[#c3c6d0] px-2 py-1 text-[10px] font-medium text-[#43474f] hover:bg-[#f2f4f6]">
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : addingNote === flag.id ? (
                        <div className="rounded-[8px] border border-[#c3c6d0] bg-white p-3 space-y-2">
                          <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)}
                            placeholder="Add an internal note…"
                            className="w-full rounded-[6px] border border-[#c3c6d0] bg-white px-2 py-1.5 text-[11px] text-[#191c1e] placeholder:text-[#737780] focus:outline-none focus:border-[#0066cc] resize-none h-16" />
                          <div className="flex gap-1.5">
                            <button onClick={() => {
                              if (noteText.trim()) {
                                addNoteMut.mutate({ flag_id: flag.id, message: noteText });
                              }
                            }}
                              disabled={!noteText.trim() || addNoteMut.isPending}
                              className="flex-1 rounded-[6px] bg-[#002d5b] px-2 py-1 text-[10px] font-semibold text-white hover:bg-[#001836] disabled:opacity-40">
                              Add Note
                            </button>
                            <button onClick={() => setAddingNote(null)}
                              className="rounded-[6px] border border-[#c3c6d0] px-2 py-1 text-[10px] font-medium text-[#43474f] hover:bg-[#f2f4f6]">
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <button onClick={() => setDraftingFlag(flag.id)}
                            className="flex-1 rounded-[6px] border border-[#c3c6d0] px-2 py-1.5 text-[10px] font-medium text-[#43474f] hover:bg-[#f2f4f6] flex items-center justify-center gap-1">
                            <Mail size={11} /> Draft Email
                          </button>
                          <button onClick={() => setAddingNote(flag.id)}
                            className="flex-1 rounded-[6px] border border-[#c3c6d0] px-2 py-1.5 text-[10px] font-medium text-[#43474f] hover:bg-[#f2f4f6]">
                            Add Note
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Bottom Row: Email generation + Email log ────────────────────────── */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

        {/* Overdue list + bulk email generation */}
        <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#eceef0]">
            <p className="text-[13px] font-semibold text-[#191c1e]">Overdue Submissions</p>
            {selectedIds.length > 0 && (
              <span className="text-[11px] font-medium text-[#0066cc]">{selectedIds.length} selected</span>
            )}
          </div>

          <div className="divide-y divide-[#f2f4f6] max-h-[300px] overflow-y-auto">
            {overdueQ.isLoading
              ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="px-5 py-3"><Skeleton className="h-10 w-full" /></div>)
              : overdueList.length === 0
              ? <p className="px-5 py-8 text-center text-[13px] text-[#737780]">No overdue submissions.</p>
              : overdueList.map((sub) => {
                  const checked = selectedIds.includes(sub.id);
                  return (
                    <label key={sub.id} className="flex items-center gap-3 px-5 py-3 hover:bg-[#f7f9fb] cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => setSelectedIds((ids) =>
                          e.target.checked ? [...ids, sub.id] : ids.filter((i) => i !== sub.id)
                        )}
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

          <div className="border-t border-[#eceef0] px-5 py-4 space-y-3">
            <div className="flex gap-2">
              <select value={templateType} onChange={(e) => setTemplateType(e.target.value)}
                className="flex-1 rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[12px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
                <option value="">Select email template…</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.template_type}>
                    {TEMPLATE_LABELS[t.template_type] ?? t.template_type}
                  </option>
                ))}
              </select>
              <button onClick={handleGenerateEmails}
                disabled={!templateType || !selectedIds.length || generating}
                className="flex items-center gap-1.5 rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#001836] disabled:opacity-40 shrink-0">
                <Mail size={12} />
                {generating ? "Generating…" : "Generate drafts"}
              </button>
            </div>
            {genResult && (
              <p className={`text-[11px] font-medium ${genResult.includes("Failed") ? "text-[#E31937]" : "text-[#1f7a4d]"}`}>
                {genResult}
              </p>
            )}
            <p className="text-[10px] text-[#737780]">
              Select overdue submissions, choose a template, and generate email drafts for manual dispatch.
            </p>
          </div>
        </div>

        {/* Email log */}
        <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
          <div className="px-5 py-4 border-b border-[#eceef0]">
            <p className="text-[13px] font-semibold text-[#191c1e]">Email Log</p>
          </div>
          <div className="divide-y divide-[#f2f4f6] max-h-[400px] overflow-y-auto">
            {emailsQ.isLoading
              ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="px-5 py-3"><Skeleton className="h-12 w-full" /></div>)
              : emails.length === 0
              ? <p className="px-5 py-8 text-center text-[13px] text-[#737780]">No emails generated yet.</p>
              : emails.map((email) => (
                  <div key={email.id} className="flex items-start gap-3 px-5 py-3">
                    <div className={`mt-1 h-2 w-2 rounded-full shrink-0 ${
                      email.status === "SENT" ? "bg-[#1f7a4d]"
                      : email.status === "DRAFT" ? "bg-[#ffd100]"
                      : "bg-[#E31937]"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-[#191c1e] truncate">{email.subject}</p>
                      <p className="text-[11px] text-[#737780]">
                        {email.provider_name} · {TEMPLATE_LABELS[email.compliance_stage] ?? email.compliance_stage}
                      </p>
                      <p className="text-[10px] text-[#737780] tabular-nums">{formatDateTime(email.generated_at)}</p>
                    </div>
                    {email.status === "DRAFT" && (
                      <button onClick={() => markSent(email.id)}
                        className="flex items-center gap-1 shrink-0 rounded-[6px] border border-[#1f7a4d] px-2 py-1 text-[10px] font-semibold text-[#1f7a4d] hover:bg-[#e5f4eb]">
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

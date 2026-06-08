"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/Toast";
import type { ReportingPeriod, ExpectedSubmission, FormTemplate, ProviderProfile } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

export default function PeriodDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [confirmActivate, setConfirmActivate] = useState(false);

  const { data: period, isLoading: periodLoading } = useQuery<ReportingPeriod>({
    queryKey: ["period", id],
    queryFn: () => api(`/periods/${id}/`),
  });

  const { data: expectedData, isLoading: esLoading } = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["period-expected", id],
    queryFn: () => api(`/expected-submissions/?period=${id}&ordering=provider_name`),
    enabled: !!period,
  });

  // All available form templates and providers (for assignment)
  const { data: allTemplates } = useQuery<{ results: FormTemplate[] }>({
    queryKey: ["form-templates-all"],
    queryFn: () => api("/form-templates/?status=ACTIVE"),
    enabled: period?.status === "DRAFT",
  });

  const { data: allProviders } = useQuery<{ results: ProviderProfile[] }>({
    queryKey: ["providers-all"],
    queryFn: () => api("/providers/?status=ACTIVE"),
    enabled: period?.status === "DRAFT",
  });

  // Currently assigned
  const { data: assignedTemplates } = useQuery<FormTemplate[]>({
    queryKey: ["period-templates", id],
    queryFn: () => api(`/periods/${id}/assigned-templates/`),
    enabled: period?.status === "DRAFT",
  });

  const { data: assignedProviders } = useQuery<ProviderProfile[]>({
    queryKey: ["period-providers", id],
    queryFn: () => api(`/periods/${id}/assigned-providers/`),
    enabled: period?.status === "DRAFT",
  });

  const assignTemplatesMut = useMutation({
    mutationFn: (ids: number[]) =>
      api(`/periods/${id}/assign-templates/`, { method: "POST", body: JSON.stringify({ template_ids: ids }) }),
    onSuccess: () => { toast("Form templates updated.", "success"); qc.invalidateQueries({ queryKey: ["period-templates", id] }); },
    onError: () => toast("Failed to update templates.", "error"),
  });

  const assignProvidersMut = useMutation({
    mutationFn: (ids: number[]) =>
      api(`/periods/${id}/assign-providers/`, { method: "POST", body: JSON.stringify({ provider_ids: ids }) }),
    onSuccess: () => { toast("Providers updated.", "success"); qc.invalidateQueries({ queryKey: ["period-providers", id] }); },
    onError: () => toast("Failed to update providers.", "error"),
  });

  const activateMutation = useMutation({
    mutationFn: () => api(`/periods/${id}/activate/`, { method: "POST" }),
    onSuccess: (data: { detail: string; expected_count: number }) => {
      toast(`Period activated — ${data.expected_count} expected submissions created.`, "success");
      setConfirmActivate(false);
      qc.invalidateQueries({ queryKey: ["period", id] });
      qc.invalidateQueries({ queryKey: ["period-expected", id] });
    },
    onError: () => toast("Failed to activate period.", "error"),
  });

  const submissions = expectedData?.results ?? [];
  const approved = submissions.filter(s => s.workflow_status === "APPROVED").length;
  const total = submissions.length;
  const completionPct = total ? Math.round((approved / total) * 100) : 0;

  const assignedTemplateIds = new Set((assignedTemplates ?? []).map(t => t.id));
  const assignedProviderIds = new Set((assignedProviders ?? []).map(p => p.id));

  function toggleTemplate(tid: number) {
    const next = new Set(assignedTemplateIds);
    next.has(tid) ? next.delete(tid) : next.add(tid);
    assignTemplatesMut.mutate(Array.from(next));
  }

  function toggleProvider(pid: number) {
    const next = new Set(assignedProviderIds);
    next.has(pid) ? next.delete(pid) : next.add(pid);
    assignProvidersMut.mutate(Array.from(next));
  }

  if (periodLoading) return (
    <div className="space-y-6"><Skeleton className="h-8 w-64" /><div className="grid grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
    </div></div>
  );
  if (!period) return <p className="text-[14px] text-[#737780]">Period not found.</p>;

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[13px] font-medium text-[#737780] mb-1">
            <Link href="/periods" className="hover:text-[#0066cc]">Periods</Link> /
          </p>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">{period.name}</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">
            {period.frequency} · {period.year}{period.month ? ` / Month ${period.month}` : ""}
          </p>
          <span className={`mt-2 inline-block rounded-full px-3 py-0.5 text-[12px] font-semibold uppercase tracking-wide ${
            period.status === "ACTIVE" ? "bg-[#e5f4eb] text-[#1f7a4d]" :
            period.status === "CLOSED" ? "bg-[#ffe8e8] text-[#c0112a]" : "bg-[#f2f4f6] text-[#43474f]"
          }`}>{period.status}</span>
        </div>

        {period.status === "DRAFT" && (
          <div>
            {confirmActivate ? (
              <div className="flex gap-2 items-center">
                <span className="text-[13px] text-[#43474f]">Activate and generate submissions?</span>
                <button onClick={() => activateMutation.mutate()} disabled={activateMutation.isPending}
                  className="rounded-[8px] bg-[#1f7a4d] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#175f3b] disabled:opacity-50">
                  {activateMutation.isPending ? "Activating…" : "Confirm Activate"}
                </button>
                <button onClick={() => setConfirmActivate(false)}
                  className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[13px] text-[#43474f] hover:bg-[#f2f4f6]">
                  Cancel
                </button>
              </div>
            ) : (
              <button onClick={() => setConfirmActivate(true)}
                disabled={assignedTemplateIds.size === 0 || assignedProviderIds.size === 0}
                title={assignedTemplateIds.size === 0 || assignedProviderIds.size === 0 ? "Assign at least one form template and one provider first" : ""}
                className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-40 disabled:cursor-not-allowed">
                Activate Period
              </button>
            )}
          </div>
        )}
      </div>

      {/* Period stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label:"Opens",          value: new Date(period.opens_at).toLocaleDateString("en-GB", { day:"numeric", month:"short", year:"numeric" }) },
          { label:"Due",            value: new Date(period.due_at).toLocaleDateString("en-GB",   { day:"numeric", month:"short", year:"numeric" }) },
          { label:"Total Expected", value: String(total) },
          { label:"Approved",       value: `${approved} / ${total} (${completionPct}%)` },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-[12px] border border-[#eceef0] bg-white px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">{label}</p>
            <p className="mt-1 text-[20px] font-bold text-[#191c1e]">{value}</p>
          </div>
        ))}
      </div>

      {/* ── DRAFT: Assignment panels ─────────────────────────────────────── */}
      {period.status === "DRAFT" && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Form Templates */}
          <div className="rounded-[16px] border border-[#eceef0] bg-white p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-semibold text-[#191c1e]">Form Templates</h2>
              <span className="text-[12px] text-[#737780]">{assignedTemplateIds.size} selected</span>
            </div>
            <p className="text-[12px] text-[#43474f] mb-3">
              Select which forms are required this period. Providers will only see forms matching their type.
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {(allTemplates?.results ?? []).map(t => (
                <label key={t.id} className="flex items-start gap-3 cursor-pointer rounded-[8px] px-3 py-2 hover:bg-[#f7f9fb]">
                  <input type="checkbox" checked={assignedTemplateIds.has(t.id)}
                    onChange={() => toggleTemplate(t.id)}
                    className="mt-0.5 h-4 w-4 accent-[#0066cc]" />
                  <div>
                    <p className="text-[13px] font-medium text-[#191c1e]">{t.name}</p>
                    <p className="text-[11px] text-[#737780]">
                      {t.form_code} · {PROVIDER_CATEGORY_LABELS[t.provider_category]} · {t.frequency}
                    </p>
                  </div>
                </label>
              ))}
              {(allTemplates?.results ?? []).length === 0 && (
                <p className="text-[13px] text-[#737780] py-4 text-center">No active form templates found.</p>
              )}
            </div>
          </div>

          {/* Providers */}
          <div className="rounded-[16px] border border-[#eceef0] bg-white p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-semibold text-[#191c1e]">Providers</h2>
              <span className="text-[12px] text-[#737780]">{assignedProviderIds.size} selected</span>
            </div>
            <p className="text-[12px] text-[#43474f] mb-3">
              Select which licensed providers must submit this period. Each provider will only receive forms matching their category.
            </p>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {(allProviders?.results ?? []).map(p => (
                <label key={p.id} className="flex items-start gap-3 cursor-pointer rounded-[8px] px-3 py-2 hover:bg-[#f7f9fb]">
                  <input type="checkbox" checked={assignedProviderIds.has(p.id)}
                    onChange={() => toggleProvider(p.id)}
                    className="mt-0.5 h-4 w-4 accent-[#0066cc]" />
                  <div>
                    <p className="text-[13px] font-medium text-[#191c1e]">{p.registered_name}</p>
                    <p className="text-[11px] text-[#737780]">{PROVIDER_CATEGORY_LABELS[p.category]}</p>
                  </div>
                </label>
              ))}
              {(allProviders?.results ?? []).length === 0 && (
                <p className="text-[13px] text-[#737780] py-4 text-center">No active providers found.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Expected Submissions table ────────────────────────────────────── */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <div className="border-b border-[#eceef0] px-6 py-4 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[#191c1e]">Expected Submissions</h2>
          {total > 0 && <span className="text-[13px] text-[#737780]">{total} total</span>}
        </div>

        {esLoading ? (
          <div className="divide-y divide-[#eceef0]">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4 flex gap-4">
                <Skeleton className="h-4 flex-1" /><Skeleton className="h-4 w-24" /><Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        ) : submissions.length === 0 ? (
          <div className="px-6 py-12 text-center text-[14px] text-[#737780]">
            {period.status === "DRAFT"
              ? "Assign form templates and providers above, then activate the period to generate submissions."
              : "No expected submissions."}
          </div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-[#f7f9fb] border-b border-[#eceef0]">
              <tr>
                {["Provider","Form","Status","Due State","Officer",""].map(h => (
                  <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eceef0]">
              {submissions.map(s => (
                <tr key={s.id} className="hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3.5 text-[13px] font-medium text-[#191c1e]">{s.provider_name}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{s.form_code}</td>
                  <td className="px-5 py-3.5"><WorkflowBadge status={s.workflow_status} /></td>
                  <td className="px-5 py-3.5"><DueStateBadge state={s.due_state} /></td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{s.assigned_officer_name ?? "—"}</td>
                  <td className="px-5 py-3.5">
                    <Link href={`/submissions?expected=${s.id}`}
                      className="text-[13px] font-medium text-[#0066cc] hover:underline">View →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

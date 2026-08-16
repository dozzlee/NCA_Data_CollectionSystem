"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Send, X } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { FormTemplate, ReportingPeriod } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS, SECTOR_LABELS } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";

interface ProviderCandidate {
  provider_id: number;
  provider_name: string;
  provider_sector: string;
  provider_category: string;
  selected: boolean;
  has_data_entry: boolean;
  has_approver: boolean;
  ready: boolean;
  mismatch: boolean;
  duplicate: boolean;
  can_assign: boolean;
  blocking_reason: string;
}

interface AssignmentPreview {
  due_at: string | null;
  providers: ProviderCandidate[];
  summary: { selected: number; assignable: number; mismatches: number; duplicates: number; not_ready: number; blocked: number };
}

interface AssignmentResult {
  created: number;
  existing: number;
  obligations_created: number;
  duplicates: number;
  recurring_schedules_created: number;
  delivery_type: "IMMEDIATE" | "SCHEDULED";
  blocked: number;
  obligations: Array<{ provider_id:number; provider_name:string; expected_submission_id:number; submission_id:number; period_id:number; period_name:string; due_at:string }>;
}

export function FormSendDialog({ template, open, onClose }: { template: FormTemplate; open: boolean; onClose: () => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [periodId, setPeriodId] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [result, setResult] = useState<AssignmentResult | null>(null);

  useEffect(() => {
    if (!open) return;
    setPeriodId("");
    setSelected([]);
    setSearch("");
    setOverrideReason("");
    setResult(null);
  }, [open, template.id]);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open, onClose]);

  const periods = useQuery<{ results: ReportingPeriod[] }>({
    queryKey: ["active-periods-for-send", template.frequency],
    queryFn: () => api(`/periods/?frequency=${template.frequency}&status=ACTIVE`),
    enabled: open,
  });
  const preview = useQuery<AssignmentPreview>({
    queryKey: ["direct-send-preview", template.id, periodId, selected, overrideReason],
    queryFn: () => api(`/form-templates/${template.id}/assignment-preview/?mode=MANUAL&provider_ids=${selected.join(",")}${periodId ? `&period=${periodId}` : ""}&override_reason=${encodeURIComponent(overrideReason)}`),
    enabled: open,
  });
  const send = useMutation<AssignmentResult>({
    mutationFn: () => api(`/form-templates/${template.id}/assignments/`, {
      method: "POST",
      body: JSON.stringify({ mode: "MANUAL", period_id: Number(periodId), provider_ids: selected, override_reason: overrideReason }),
    }),
    onSuccess: (result) => {
      if (result.delivery_type !== "IMMEDIATE") {
        toast("The server did not create an immediate provider obligation.", "error");
        return;
      }
      setResult(result);
      toast(result.obligations_created ? `${result.obligations_created} provider form${result.obligations_created === 1 ? "" : "s"} sent.` : "Already sent for the selected provider and period.", "success");
      queryClient.invalidateQueries({ queryKey: ["form-assignments", template.id] });
      queryClient.invalidateQueries({ queryKey: ["direct-send-preview", template.id] });
      queryClient.invalidateQueries({ queryKey: ["expected-submissions"] });
    },
    onError: (error: Error) => toast(error.message, "error"),
  });

  const candidates = useMemo(() => preview.data?.providers ?? [], [preview.data?.providers]);
  const visibleCandidates = useMemo(() => {
    const term = search.trim().toLowerCase();
    return term ? candidates.filter(item => `${item.provider_name} ${item.provider_category} ${item.provider_sector}`.toLowerCase().includes(term)) : candidates;
  }, [candidates, search]);
  const selectedRows = candidates.filter(item => selected.includes(item.provider_id));
  const selectedMismatches = selectedRows.filter(item => item.mismatch);
  const selectedBlocked = selectedRows.some(item => !item.ready || item.duplicate || (item.mismatch && !overrideReason.trim()));
  const canSend = Boolean(periodId && selected.length && !selectedBlocked && !send.isPending && !preview.isFetching);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm" onMouseDown={event => event.target === event.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="send-form-title" className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b px-6 py-5">
          <div>
            <p className="font-mono text-xs font-semibold text-[#0066cc]">{template.form_code} · Version {template.version}</p>
            <h2 id="send-form-title" className="mt-1 text-xl font-semibold text-[#191c1e]">Send {template.name}</h2>
            <p className="mt-1 text-xs text-[#737780]">Select one active reporting period and every provider that should receive this exact version.</p>
          </div>
          <button onClick={onClose} aria-label="Close send form dialog" className="rounded-lg p-2 text-[#737780] hover:bg-[#f2f4f6]"><X size={18}/></button>
        </div>

        <div className="overflow-y-auto px-6 py-5">
          <label className="block text-xs font-semibold uppercase tracking-wide text-[#737780]">Reporting period</label>
          <select value={periodId} onChange={event => setPeriodId(event.target.value)} className="mt-1 w-full rounded-lg border border-[#c3c6d0] px-3 py-2.5 text-sm focus:border-[#0066cc] focus:outline-none">
            <option value="">Select an active {template.frequency.toLowerCase().replace("_", "-")} period</option>
            {(periods.data?.results ?? []).map(period => <option key={period.id} value={period.id}>{period.name} · due {new Date(period.due_at).toLocaleDateString()}</option>)}
          </select>
          {!periods.isLoading && !(periods.data?.results ?? []).length && <p className="mt-2 text-xs text-amber-700">There is no active reporting period matching this form’s frequency.</p>}

          <div className="mt-5 flex items-end justify-between gap-3">
            <div><h3 className="text-sm font-semibold">Providers</h3><p className="mt-0.5 text-xs text-[#737780]">Providers without both portal roles remain visible but cannot receive the form.</p></div>
            <label className="relative w-full max-w-xs"><span className="sr-only">Search providers</span><Search className="absolute left-3 top-2.5 text-[#737780]" size={16}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search providers" className="w-full rounded-lg border border-[#c3c6d0] py-2 pl-9 pr-3 text-sm focus:border-[#0066cc] focus:outline-none"/></label>
          </div>

          <div className="mt-3 max-h-72 overflow-y-auto rounded-xl border border-[#eceef0]">
            {preview.isLoading ? <p className="p-5 text-sm text-[#737780]">Loading providers…</p> : visibleCandidates.map(provider => {
              const disabled = !provider.ready || Boolean(periodId && provider.duplicate);
              return <label key={provider.provider_id} className={`flex items-start gap-3 border-b border-[#eceef0] p-3 last:border-0 ${disabled ? "bg-[#f7f9fb] text-[#737780]" : "cursor-pointer hover:bg-[#f7f9fb]"}`}>
                <input type="checkbox" className="mt-1" disabled={disabled} checked={selected.includes(provider.provider_id)} onChange={() => setSelected(current => current.includes(provider.provider_id) ? current.filter(id => id !== provider.provider_id) : [...current, provider.provider_id])}/>
                <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{provider.provider_name}</span><span className="mt-0.5 block text-xs">{SECTOR_LABELS[provider.provider_sector as keyof typeof SECTOR_LABELS] ?? provider.provider_sector} · {PROVIDER_CATEGORY_LABELS[provider.provider_category as keyof typeof PROVIDER_CATEGORY_LABELS] ?? provider.provider_category}</span>{provider.blocking_reason && <span className="mt-1 block text-xs text-amber-700">{provider.blocking_reason}</span>}</span>
                <span className="flex flex-wrap justify-end gap-1">{provider.ready ? <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">Accounts ready</span> : <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">Accounts missing</span>}{provider.mismatch && <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">Type mismatch</span>}{provider.duplicate && <span className="rounded bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700">Already sent</span>}</span>
              </label>;
            })}
            {!preview.isLoading && !visibleCandidates.length && <p className="p-5 text-sm text-[#737780]">No active providers match your search.</p>}
          </div>

          {selectedMismatches.length > 0 && <div className="mt-4"><label className="block text-xs font-semibold uppercase tracking-wide text-[#737780]">Mismatch override reason</label><textarea value={overrideReason} onChange={event => setOverrideReason(event.target.value)} rows={2} placeholder="Explain why this form should be sent across a sector or provider-type mismatch" className="mt-1 w-full rounded-lg border border-[#c3c6d0] p-3 text-sm focus:border-[#0066cc] focus:outline-none"/></div>}

          <div className="mt-4 rounded-xl bg-[#f7f9fb] p-4 text-xs text-[#43474f]">
            <span className="font-semibold">Confirmation:</span> {selected.length} selected · {preview.data?.summary.assignable ?? 0} ready to send · {preview.data?.summary.duplicates ?? 0} already sent · {preview.data?.summary.mismatches ?? 0} mismatches
            {periodId && preview.data?.due_at && <span> · deadline {new Date(preview.data.due_at).toLocaleString()}</span>}
          </div>
          {result && <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-semibold text-emerald-900">{result.obligations_created ? "Form delivered to the provider portal" : "Already sent"}</p>
            {result.obligations.map(obligation => <div key={obligation.expected_submission_id} className="mt-3 rounded-lg bg-white p-3 text-xs text-[#43474f]">
              <p className="font-semibold text-[#191c1e]">{obligation.provider_name} · {obligation.period_name}</p>
              <p className="mt-1">Due {new Date(obligation.due_at).toLocaleString()}</p>
              <div className="mt-2 flex gap-4">
                <Link className="font-semibold text-[#0066cc]" href={`/submissions?provider=${obligation.provider_id}&period=${obligation.period_id}`}>View obligation</Link>
                <Link className="font-semibold text-[#0066cc]" href={`/periods/${obligation.period_id}`}>View reporting period</Link>
              </div>
            </div>)}
            {result.duplicates > 0 && <p className="mt-2 text-xs text-emerald-900">{result.duplicates} selection{result.duplicates === 1 ? " was" : "s were"} already sent.</p>}
          </div>}
        </div>

        <div className="flex justify-end gap-3 border-t px-6 py-4"><button onClick={onClose} className="rounded-lg border border-[#c3c6d0] px-4 py-2 text-sm">{result ? "Close" : "Cancel"}</button>{!result && <button onClick={() => send.mutate()} disabled={!canSend} className="inline-flex items-center gap-2 rounded-lg bg-[#001836] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"><Send size={15}/>{send.isPending ? "Sending…" : "Confirm & send"}</button>}</div>
      </div>
    </div>
  );
}

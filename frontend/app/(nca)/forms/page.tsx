"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { FormTemplate, ProviderCategory, Frequency } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

const CATEGORIES: ProviderCategory[] = ["MNO","ISP","PAY_TV","TOWER_OPERATOR","TOWER_MAIN","DOMESTIC_FIBRE","SUBMARINE_FIBRE"];
const FREQUENCIES: Frequency[] = ["MONTHLY","SEMI_ANNUAL","ANNUAL"];
const FREQ_LABELS: Record<Frequency, string> = { MONTHLY:"Monthly", SEMI_ANNUAL:"Semi-Annual", ANNUAL:"Annual" };
const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-[#e5f4eb] text-[#1f7a4d]",
  DRAFT:  "bg-[#fff3bf] text-[#7a5c00]",
  ARCHIVED: "bg-[#f2f4f6] text-[#737780]",
};

interface NewFormState {
  form_code: string; name: string; provider_category: ProviderCategory;
  frequency: Frequency; version: string;
}
const EMPTY: NewFormState = {
  form_code:"", name:"", provider_category:"MNO", frequency:"MONTHLY", version:"1.0"
};

export default function FormsPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<NewFormState>(EMPTY);
  const [filterCat, setFilterCat] = useState("");

  const { data, isLoading } = useQuery<{ results: FormTemplate[] }>({
    queryKey: ["form-templates", filterCat],
    queryFn: () => api(`/form-templates/${filterCat ? `?provider_category=${filterCat}` : ""}`),
  });

  const createMutation = useMutation({
    mutationFn: (d: NewFormState) =>
      api("/form-templates/", { method:"POST", body: JSON.stringify({ ...d, status:"DRAFT", effective_from: new Date().toISOString().split("T")[0], kmz_required: false }) }),
    onSuccess: () => {
      toast("Form template created.", "success");
      setShowCreate(false); setForm(EMPTY);
      qc.invalidateQueries({ queryKey: ["form-templates"] });
    },
    onError: () => toast("Failed to create template.", "error"),
  });

  const templates = data?.results ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">Form Templates</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">
            Manage data collection forms, sections, and indicators. Provider types are fixed; templates and fields are fully configurable.
          </p>
        </div>
        <button onClick={() => setShowCreate(v => !v)}
          className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b]">
          {showCreate ? "Cancel" : "+ New Template"}
        </button>
      </div>

      {showCreate && (
        <form onSubmit={e => { e.preventDefault(); createMutation.mutate(form); }}
          className="rounded-[16px] border border-[#eceef0] bg-white p-6 space-y-4">
          <h2 className="text-[15px] font-semibold text-[#191c1e]">New Form Template</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { key:"form_code", label:"Form Code", placeholder:"e.g. DC-ISP07" },
              { key:"name",      label:"Form Name",  placeholder:"e.g. ISP Annual Return v2" },
              { key:"version",   label:"Version",    placeholder:"1.0" },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">{label}</label>
                <input type="text" placeholder={placeholder} required
                  value={(form as any)[key]}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none" />
              </div>
            ))}
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Provider Type</label>
              <select value={form.provider_category}
                onChange={e => setForm(f => ({ ...f, provider_category: e.target.value as ProviderCategory }))}
                className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
                {CATEGORIES.map(c => <option key={c} value={c}>{PROVIDER_CATEGORY_LABELS[c]}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Frequency</label>
              <select value={form.frequency}
                onChange={e => setForm(f => ({ ...f, frequency: e.target.value as Frequency }))}
                className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
                {FREQUENCIES.map(f => <option key={f} value={f}>{FREQ_LABELS[f]}</option>)}
              </select>
            </div>
          </div>
          <button type="submit" disabled={createMutation.isPending}
            className="rounded-[8px] bg-[#001836] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
            {createMutation.isPending ? "Creating…" : "Create Template"}
          </button>
        </form>
      )}

      {/* Filter */}
      <div className="flex gap-3">
        <select value={filterCat} onChange={e => setFilterCat(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
          <option value="">All provider types</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{PROVIDER_CATEGORY_LABELS[c]}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <table className="w-full text-left">
          <thead className="border-b border-[#eceef0] bg-[#f7f9fb]">
            <tr>
              {["Code","Name","Provider Type","Frequency","Version","Status","Sections",""].map(h => (
                <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eceef0]">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-5 py-3.5"><Skeleton className="h-3.5 w-full" /></td>
                  ))}</tr>
                ))
              : templates.map(t => (
                <tr key={t.id} className="hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3.5 font-mono text-[12px] font-semibold text-[#0066cc]">{t.form_code}</td>
                  <td className="px-5 py-3.5 text-[13px] font-medium text-[#191c1e]">{t.name}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{PROVIDER_CATEGORY_LABELS[t.provider_category]}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{FREQ_LABELS[t.frequency as Frequency]}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{t.version}</td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STATUS_COLORS[t.status]}`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-[#737780]">—</td>
                  <td className="px-5 py-3.5">
                    <Link href={`/forms/${t.id}`} className="text-[13px] font-medium text-[#0066cc] hover:underline">
                      Build →
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

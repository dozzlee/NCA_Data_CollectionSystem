"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { FormSendDialog } from "@/components/forms/FormSendDialog";
import type { FormTemplate, FormWorkbookImport, FormCodeCatalogEntry, Frequency, ProviderCategory } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS, SECTOR_LABELS } from "@/lib/utils";

const CATEGORIES: ProviderCategory[] = ["MNO","ISP","PAY_TV","TOWER_OPERATOR","TOWER_MAIN","DOMESTIC_FIBRE","SUBMARINE_FIBRE"];
const FREQ_LABELS: Record<Frequency, string> = { MONTHLY:"Monthly", QUARTERLY:"Quarterly", SEMI_ANNUAL:"Bi-annual", ANNUAL:"Annual" };
const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-[#e5f4eb] text-[#1f7a4d]",
  DRAFT:  "bg-[#fff3bf] text-[#7a5c00]",
  ARCHIVED: "bg-[#f2f4f6] text-[#737780]",
};

interface NewFormState {
  form_code: string;
  version: string;
  frequency: Frequency | "";
}
const EMPTY: NewFormState = {
  form_code:"", version:"", frequency:""
};

export default function FormsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<NewFormState>(EMPTY);
  const [workbook, setWorkbook] = useState<File | null>(null);
  const [filterCat, setFilterCat] = useState("");
  const [filterSector, setFilterSector] = useState("");
  const [sendTemplate, setSendTemplate] = useState<FormTemplate | null>(null);

  const catalog = useQuery<{ results: FormCodeCatalogEntry[] }>({
    queryKey: ["form-code-catalog"],
    queryFn: () => api("/form-code-catalog/"),
  });

  const { data, isLoading } = useQuery<{ results: FormTemplate[] }>({
    queryKey: ["form-templates", filterCat, filterSector],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filterCat) params.set("provider_category", filterCat);
      if (filterSector) params.set("sector", filterSector);
      return api(`/form-templates/${params.size ? `?${params}` : ""}`);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (d: NewFormState) => {
      if (workbook) {
        const payload = new FormData();
        Object.entries(d).forEach(([key, value]) => payload.append(key, value));
        payload.append("file", workbook);
        return api.upload<FormWorkbookImport>("/form-workbook-imports/", payload);
      }
      return api<FormTemplate>("/form-templates/", { method:"POST", body: JSON.stringify({ ...d, effective_from: new Date().toISOString().split("T")[0], kmz_required: false }) });
    },
    onSuccess: (result) => {
      const message = "detected_schema" in result
        ? result.parse_status === "PENDING"
          ? "Workbook uploaded. Analysis is continuing in the preview."
          : "Workbook parsed. Review the generated structure."
        : "Form template created.";
      toast(message, "success");
      setShowCreate(false); setForm(EMPTY);
      setWorkbook(null);
      qc.invalidateQueries({ queryKey: ["form-templates"] });
      router.push("detected_schema" in result ? `/forms/imports/${result.id}` : `/forms/${result.id}`);
    },
    onError: (error: Error) => toast(error.message || "Failed to create template.", "error"),
  });

  const templates = data?.results ?? [];
  const selectedCode = catalog.data?.results.find(item => item.code === form.form_code);

  function selectFormCode(code: string) {
    const selected = catalog.data?.results.find(item => item.code === code);
    setForm({ form_code: code, version: selected?.next_version ?? "", frequency: "" });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">Form Templates</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">
            Select a governed form code, then create its independent structure manually or from its source workbook.
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
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Form Code</label>
              <select value={form.form_code} required onChange={e => selectFormCode(e.target.value)}
                className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
                <option value="">Select a form code</option>
                {catalog.data?.results.map(item => <option key={item.code} value={item.code}>{item.code}{item.code_status === "PROVISIONAL" ? " (Provisional)" : ""}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Form Name</label>
              <div className="mt-1 min-h-10 rounded-[8px] border border-[#d8dbe2] bg-[#f7f9fb] px-3 py-2 text-[13px] text-[#43474f]">
                {selectedCode?.name ?? "Select a form code"}
              </div>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Version</label>
              <div className="mt-1 min-h-10 rounded-[8px] border border-[#d8dbe2] bg-[#f7f9fb] px-3 py-2 text-[13px] text-[#43474f]">
                {form.version || "Select a form code"}
              </div>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Frequency</label>
              <select value={form.frequency} required onChange={e => setForm(v => ({ ...v, frequency: e.target.value as Frequency }))}
                className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
                <option value="">Select frequency</option>
                {(["MONTHLY", "QUARTERLY", "SEMI_ANNUAL", "ANNUAL"] as Frequency[]).map(value => <option key={value} value={value}>{FREQ_LABELS[value]}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2 lg:col-span-3 rounded-[10px] border border-dashed border-[#9aa5b1] bg-[#f7f9fb] p-4">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Generate from source file (optional)</label>
              <input type="file" accept=".xlsx,.pdf,.docx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={e => setWorkbook(e.target.files?.[0] ?? null)}
                className="mt-2 block w-full text-[13px] text-[#43474f] file:mr-3 file:rounded-[8px] file:border-0 file:bg-[#e8f1fb] file:px-3 file:py-2 file:font-semibold file:text-[#004999]" />
              <p className="mt-2 text-[11px] text-[#737780]">Up to 20 MB. Excel structure, or PDF/Word text, is imported for review; source values never become provider answers.</p>
              {selectedCode?.code === "MNO-MONTHLY" && <p className="mt-2 text-[11px] font-medium text-[#8a4b08]">MNO-MONTHLY uses its dedicated workbook-driven creation workflow. Upload the approved MNO workbook to continue.</p>}
              {workbook && <p className="mt-2 text-xs font-medium text-[#191c1e]">Selected: {workbook.name} · {(workbook.size / 1024 / 1024).toFixed(1)} MB</p>}
            </div>
          </div>
          {createMutation.isPending && workbook && (
            <div role="status" className="rounded-[10px] border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
              <p className="font-semibold">Uploading and analyzing the workbook…</p>
              <p className="mt-1 text-xs">Each visible worksheet is being converted into a form section. Large workbooks with many formatted tabs can take up to two minutes; keep this page open.</p>
            </div>
          )}
          <button type="submit" disabled={createMutation.isPending || !selectedCode || !form.version || !form.frequency || (selectedCode?.code === "MNO-MONTHLY" && !workbook)}
            className="rounded-[8px] bg-[#001836] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
            {createMutation.isPending ? (workbook ? "Analyzing workbook…" : "Creating…") : workbook ? "Upload & Preview" : "Create Template"}
          </button>
        </form>
      )}

      {/* Filter */}
      <div className="flex gap-3">
        <select value={filterSector} onChange={e => setFilterSector(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
          <option value="">All sectors</option>
          {Object.entries(SECTOR_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
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
              {["Code","Name","Sector","Provider Type","Frequency","Version","Status",""].map(h => (
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
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{SECTOR_LABELS[t.sector]}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{PROVIDER_CATEGORY_LABELS[t.provider_category]}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{FREQ_LABELS[t.frequency as Frequency]}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{t.version}</td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STATUS_COLORS[t.status]}`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <Link href={`/forms/${t.id}`} className="rounded-lg border border-[#c3c6d0] px-3 py-1.5 text-[12px] font-semibold text-[#43474f] hover:bg-[#f2f4f6]">Open</Link>
                      <button type="button" onClick={() => setSendTemplate(t)} disabled={t.status!=="ACTIVE"||t.approval_status!=="APPROVED"} title={t.status!=="ACTIVE"||t.approval_status!=="APPROVED"?"Only active, approved templates can be sent.":"Send this exact template version to providers"} className="rounded-lg bg-[#0066cc] px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-[#0056ad] disabled:cursor-not-allowed disabled:bg-[#c3c6d0]">Send</button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {sendTemplate&&<FormSendDialog template={sendTemplate} open onClose={()=>setSendTemplate(null)}/>}
    </div>
  );
}

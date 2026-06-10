"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { FormTemplate, FormSection, FormField, FieldType } from "@/lib/types";
import { ChevronDown, ChevronRight, Plus, Trash2, GripVertical } from "lucide-react";

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value:"text",        label:"Text" },
  { value:"number",      label:"Number" },
  { value:"currency",    label:"Currency (GH₵)" },
  { value:"percentage",  label:"Percentage (%)" },
  { value:"date",        label:"Date" },
  { value:"boolean",     label:"Yes / No" },
  { value:"select",      label:"Dropdown (Select)" },
  { value:"multiselect", label:"Multi-select" },
  { value:"textarea",    label:"Text Area" },
  { value:"coordinate",  label:"Coordinate (lat/lng)" },
  { value:"formula",     label:"Formula (calculated)" },
  { value:"declaration", label:"Declaration (checkbox)" },
];

const inp = "w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20";
const lbl = "block text-[11px] font-semibold uppercase tracking-wide text-[#737780] mb-1";

function AddFieldForm({ templateId, sectionId, onDone }: { templateId: string; sectionId: number; onDone: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [d, setD] = useState({ field_code:"", label:"", field_type:"text" as FieldType, unit:"", is_required:true, help_text:"" });

  const mut = useMutation({
    mutationFn: () => api(`/form-templates/${templateId}/sections/${sectionId}/fields/`, {
      method:"POST", body: JSON.stringify(d)
    }),
    onSuccess: () => {
      toast("Field added.", "success");
      qc.invalidateQueries({ queryKey: ["form-template", templateId] });
      setD({ field_code:"", label:"", field_type:"text", unit:"", is_required:true, help_text:"" });
      onDone();
    },
    onError: () => toast("Failed to add field.", "error"),
  });

  return (
    <div className="mt-3 rounded-[10px] border border-[#c3c6d0] bg-[#f7f9fb] p-4 space-y-3">
      <p className="text-[12px] font-semibold text-[#191c1e]">Add Field</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div>
          <label className={lbl}>Field Code</label>
          <input className={inp} placeholder="e.g. total_subs" value={d.field_code}
            onChange={e => setD(p => ({ ...p, field_code: e.target.value }))} />
        </div>
        <div className="sm:col-span-2">
          <label className={lbl}>Label / Question</label>
          <input className={inp} placeholder="e.g. Total Active Subscribers" value={d.label}
            onChange={e => setD(p => ({ ...p, label: e.target.value }))} />
        </div>
        <div>
          <label className={lbl}>Field Type</label>
          <select className={inp} value={d.field_type}
            onChange={e => setD(p => ({ ...p, field_type: e.target.value as FieldType }))}>
            {FIELD_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div>
          <label className={lbl}>Unit (optional)</label>
          <input className={inp} placeholder="e.g. GH₵, Mbps, km, %" value={d.unit}
            onChange={e => setD(p => ({ ...p, unit: e.target.value }))} />
        </div>
        <div className="flex items-end gap-2 pb-0.5">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={d.is_required}
              onChange={e => setD(p => ({ ...p, is_required: e.target.checked }))}
              className="h-4 w-4 accent-[#0066cc]" />
            <span className="text-[13px] text-[#191c1e]">Required</span>
          </label>
        </div>
        <div className="sm:col-span-3">
          <label className={lbl}>Help Text (optional)</label>
          <input className={inp} placeholder="Guidance shown below the field" value={d.help_text}
            onChange={e => setD(p => ({ ...p, help_text: e.target.value }))} />
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={() => mut.mutate()} disabled={mut.isPending || !d.field_code || !d.label}
          className="rounded-[8px] bg-[#001836] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
          {mut.isPending ? "Adding…" : "Add Field"}
        </button>
        <button onClick={onDone} className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[12px] text-[#43474f] hover:bg-[#f2f4f6]">
          Cancel
        </button>
      </div>
    </div>
  );
}

function AddGridForm({ templateId, sectionId, onDone }: { templateId: string; sectionId: number; onDone: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [d, setD] = useState({ grid_code:"", title:"", row_mode:"REPEATABLE" as "FIXED"|"REPEATABLE" });

  const mut = useMutation({
    mutationFn: () => api(`/form-templates/${templateId}/sections/${sectionId}/grids/`, {
      method:"POST", body: JSON.stringify(d)
    }),
    onSuccess: () => {
      toast("Grid added.", "success");
      qc.invalidateQueries({ queryKey: ["form-template", templateId] });
      setD({ grid_code:"", title:"", row_mode:"REPEATABLE" });
      onDone();
    },
    onError: () => toast("Failed to add grid.", "error"),
  });

  return (
    <div className="mt-3 rounded-[10px] border border-[#c3c6d0] bg-[#f7f9fb] p-4 space-y-3">
      <p className="text-[12px] font-semibold text-[#191c1e]">Add Grid / Table</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={lbl}>Grid Code</label>
          <input className={inp} placeholder="e.g. UPSTREAM_PROVIDERS" value={d.grid_code}
            onChange={e => setD(p => ({ ...p, grid_code: e.target.value }))} />
        </div>
        <div>
          <label className={lbl}>Grid Title</label>
          <input className={inp} placeholder="e.g. Upstream Internet Access Providers" value={d.title}
            onChange={e => setD(p => ({ ...p, title: e.target.value }))} />
        </div>
        <div>
          <label className={lbl}>Row Mode</label>
          <select className={inp} value={d.row_mode}
            onChange={e => setD(p => ({ ...p, row_mode: e.target.value as "FIXED"|"REPEATABLE" }))}>
            <option value="REPEATABLE">Repeatable — providers add rows</option>
            <option value="FIXED">Fixed — pre-defined rows (e.g. regions)</option>
          </select>
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={() => mut.mutate()} disabled={mut.isPending || !d.grid_code || !d.title}
          className="rounded-[8px] bg-[#001836] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
          {mut.isPending ? "Adding…" : "Add Grid"}
        </button>
        <button onClick={onDone} className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[12px] text-[#43474f] hover:bg-[#f2f4f6]">
          Cancel
        </button>
      </div>
    </div>
  );
}

function SectionBlock({ section, templateId }: { section: FormSection & { grids?: unknown[] }; templateId: string }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [addingField, setAddingField] = useState(false);
  const [addingGrid, setAddingGrid] = useState(false);

  const deleteFieldMut = useMutation({
    mutationFn: (fid: number) =>
      api(`/form-templates/${templateId}/sections/${section.id}/fields/${fid}/`, { method:"DELETE" }),
    onSuccess: () => { toast("Field removed.", "info"); qc.invalidateQueries({ queryKey: ["form-template", templateId] }); },
    onError: () => toast("Failed to remove field.", "error"),
  });

  const deleteSectionMut = useMutation({
    mutationFn: () =>
      api(`/form-templates/${templateId}/sections/${section.id}/`, { method:"DELETE" }),
    onSuccess: () => { toast("Section removed.", "info"); qc.invalidateQueries({ queryKey: ["form-template", templateId] }); },
    onError: () => toast("Cannot delete — section may have submission data.", "error"),
  });

  return (
    <div className="rounded-[12px] border border-[#eceef0] bg-white overflow-hidden">
      {/* Section header */}
      <div className="flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-[#f7f9fb] transition-colors"
        onClick={() => setOpen(v => !v)}>
        <GripVertical size={14} className="text-[#c3c6d0] shrink-0" />
        <button className="text-[#43474f] hover:text-[#191c1e]">
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
        <div className="flex-1 min-w-0">
          <span className="text-[13px] font-semibold text-[#191c1e]">{section.title}</span>
          <span className="ml-2 text-[11px] font-mono text-[#737780]">{section.section_code}</span>
        </div>
        <span className="shrink-0 text-[11px] text-[#737780]">
          {section.fields.length} field{section.fields.length !== 1 ? "s" : ""}
          {(section as { grids?: unknown[] }).grids?.length ? ` · ${(section as { grids?: unknown[] }).grids!.length} grid${(section as { grids?: unknown[] }).grids!.length !== 1 ? "s" : ""}` : ""}
        </span>
        <button onClick={e => { e.stopPropagation(); if (confirm(`Delete section "${section.title}"?`)) deleteSectionMut.mutate(); }}
          className="ml-2 text-[#737780] hover:text-[#e31937] transition-colors">
          <Trash2 size={14} />
        </button>
      </div>

      {open && (
        <div className="border-t border-[#eceef0] px-5 pb-4 pt-3 space-y-2">
          {section.instructions && (
            <p className="text-[12px] text-[#43474f] italic mb-3">{section.instructions}</p>
          )}

          {/* Fields list */}
          {section.fields.length > 0 && (
            <div className="space-y-1 mb-3">
              {section.fields.map((field: FormField) => (
                <div key={field.id} className="flex items-center gap-3 rounded-[8px] bg-[#f7f9fb] px-3 py-2">
                  <span className="text-[12px] font-medium text-[#191c1e] flex-1">{field.label}</span>
                  <span className="text-[10px] font-mono text-[#737780] bg-white border border-[#eceef0] rounded px-1.5 py-0.5">{field.field_type}</span>
                  {field.unit && <span className="text-[10px] text-[#737780]">{field.unit}</span>}
                  {field.is_required && <span className="text-[10px] text-[#e31937]">*</span>}
                  <button onClick={() => { if (confirm(`Remove field "${field.label}"?`)) deleteFieldMut.mutate(field.id); }}
                    className="text-[#c3c6d0] hover:text-[#e31937] transition-colors ml-1">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Grids list */}
          {(section as { grids?: { id: number; title: string; row_mode: string; columns: { id: number; label: string }[] }[] }).grids?.map(grid => (
            <div key={grid.id} className="rounded-[8px] border border-[#c3c6d0] bg-[#f7f9fb] px-3 py-2 mb-2">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[12px] font-semibold text-[#191c1e]">⊞ {grid.title}</span>
                <span className="text-[10px] text-[#737780] bg-white border border-[#eceef0] rounded px-1.5 py-0.5">{grid.row_mode}</span>
                <span className="text-[10px] text-[#737780] ml-auto">{grid.columns.length} column{grid.columns.length !== 1 ? "s" : ""}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {grid.columns.map(c => (
                  <span key={c.id} className="text-[10px] bg-white border border-[#eceef0] rounded px-1.5 py-0.5 text-[#43474f]">{c.label}</span>
                ))}
              </div>
            </div>
          ))}

          {/* Add field / grid buttons */}
          {!addingField && !addingGrid && (
            <div className="flex gap-2 pt-1">
              <button onClick={() => setAddingField(true)}
                className="flex items-center gap-1.5 rounded-[8px] border border-[#c3c6d0] px-3 py-1.5 text-[12px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors">
                <Plus size={12} /> Add Field
              </button>
              <button onClick={() => setAddingGrid(true)}
                className="flex items-center gap-1.5 rounded-[8px] border border-[#c3c6d0] px-3 py-1.5 text-[12px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors">
                <Plus size={12} /> Add Grid / Table
              </button>
            </div>
          )}

          {addingField && <AddFieldForm templateId={templateId} sectionId={section.id} onDone={() => setAddingField(false)} />}
          {addingGrid && <AddGridForm templateId={templateId} sectionId={section.id} onDone={() => setAddingGrid(false)} />}
        </div>
      )}
    </div>
  );
}

export default function FormBuilderPage() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [addingSection, setAddingSection] = useState(false);
  const [newSection, setNewSection] = useState({ section_code:"", title:"", instructions:"" });

  const { data: template, isLoading } = useQuery<FormTemplate & { sections: (FormSection & { grids: unknown[] })[] }>({
    queryKey: ["form-template", id],
    queryFn: () => api(`/form-templates/${id}/`),
  });

  const addSectionMut = useMutation({
    mutationFn: (d: typeof newSection) =>
      api(`/form-templates/${id}/sections/`, { method:"POST", body: JSON.stringify(d) }),
    onSuccess: () => {
      toast("Section added.", "success");
      qc.invalidateQueries({ queryKey: ["form-template", id] });
      setNewSection({ section_code:"", title:"", instructions:"" });
      setAddingSection(false);
    },
    onError: () => toast("Failed to add section.", "error"),
  });

  const activateMut = useMutation({
    mutationFn: () => api(`/form-templates/${id}/`, { method:"PATCH", body: JSON.stringify({ status:"ACTIVE" }) }),
    onSuccess: () => { toast("Template set to Active.", "success"); qc.invalidateQueries({ queryKey: ["form-template", id] }); },
  });

  if (isLoading) return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-[12px]" />)}
    </div>
  );
  if (!template) return <p className="text-[14px] text-[#737780]">Template not found.</p>;

  const sections = template.sections ?? [];

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back nav */}
      <a href="/forms"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
        ← Back to Form Templates
      </a>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-mono font-semibold text-[#0066cc] mb-1">{template.form_code}</p>
          <h1 className="text-[26px] font-semibold text-[#191c1e]">{template.name}</h1>
          <p className="text-[13px] text-[#43474f] mt-0.5">
            {template.provider_category} · {template.frequency} · v{template.version}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          {template.status !== "ACTIVE" && (
            <button onClick={() => activateMut.mutate()}
              className="rounded-[8px] bg-[#1f7a4d] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#175f3b]">
              Set Active
            </button>
          )}
          {template.status === "ACTIVE" && (
            <span className="rounded-full bg-[#e5f4eb] px-3 py-1.5 text-[12px] font-semibold text-[#1f7a4d]">● Active</span>
          )}
        </div>
      </div>

      {/* Section count */}
      <div className="flex items-center justify-between">
        <p className="text-[14px] text-[#43474f]">
          <span className="font-semibold text-[#191c1e]">{sections.length}</span> section{sections.length !== 1 ? "s" : ""}
        </p>
        <button onClick={() => setAddingSection(v => !v)}
          className="flex items-center gap-1.5 rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b]">
          <Plus size={14} /> {addingSection ? "Cancel" : "Add Section"}
        </button>
      </div>

      {/* Add section form */}
      {addingSection && (
        <div className="rounded-[12px] border border-[#eceef0] bg-white p-5 space-y-3">
          <p className="text-[13px] font-semibold text-[#191c1e]">New Section</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>Section Code</label>
              <input className={inp} placeholder="e.g. UPSTREAM_TRANSIT" value={newSection.section_code}
                onChange={e => setNewSection(p => ({ ...p, section_code: e.target.value.toUpperCase().replace(/\s/g,"_") }))} />
            </div>
            <div>
              <label className={lbl}>Section Title</label>
              <input className={inp} placeholder="e.g. Upstream Transit" value={newSection.title}
                onChange={e => setNewSection(p => ({ ...p, title: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <label className={lbl}>Instructions (optional)</label>
              <textarea className={inp} rows={2} placeholder="Guidance shown to providers at the top of this section"
                value={newSection.instructions}
                onChange={e => setNewSection(p => ({ ...p, instructions: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => addSectionMut.mutate(newSection)}
              disabled={addSectionMut.isPending || !newSection.section_code || !newSection.title}
              className="rounded-[8px] bg-[#001836] px-4 py-2 text-[12px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
              {addSectionMut.isPending ? "Adding…" : "Add Section"}
            </button>
            <button onClick={() => setAddingSection(false)}
              className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[12px] text-[#43474f] hover:bg-[#f2f4f6]">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Sections */}
      {sections.length === 0 ? (
        <div className="rounded-[16px] border-2 border-dashed border-[#c3c6d0] py-16 text-center">
          <p className="text-[14px] text-[#737780]">No sections yet.</p>
          <p className="text-[13px] text-[#737780] mt-1">Add a section to start building this form.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sections.map((s, idx) => (
            <div key={s.id} className="flex items-start gap-3">
              <span className="mt-3.5 text-[11px] font-bold text-[#737780] w-6 text-right shrink-0">{idx + 1}</span>
              <div className="flex-1">
                <SectionBlock section={s} templateId={id} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

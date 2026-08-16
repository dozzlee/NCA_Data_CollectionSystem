"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { FormSendDialog } from "@/components/forms/FormSendDialog";
import type { FormTemplate, FormSection, FormHeading, FormField, FormGrid, FieldType, ProviderProfile, ReportingPeriod } from "@/lib/types";
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

function AssignmentPanel({ template }: { template: FormTemplate }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [mode,setMode]=useState<"RECURRING"|"MANUAL">("MANUAL");
  const [sendOpen,setSendOpen]=useState(false);
  const [selected,setSelected]=useState<number[]>([]);
  const [periodId,setPeriodId]=useState("");
  const [effectiveFrom,setEffectiveFrom]=useState(new Date().toISOString().slice(0,10));
  const [effectiveTo,setEffectiveTo]=useState("");
  const [overrideReason,setOverrideReason]=useState("");
  const providers=useQuery<{results:ProviderProfile[]}>({queryKey:["providers-for-form",template.id],queryFn:()=>api(`/providers/?status=ACTIVE`)});
  const periods=useQuery<{results:ReportingPeriod[]}>({queryKey:["periods-for-form",template.id],queryFn:()=>api(`/periods/?frequency=${template.frequency}`)});
  const assignments=useQuery<{recurring:Array<{id:number;provider_name:string;effective_from:string;effective_to:string|null}>;manual:Array<{id:number;provider_name:string;period_name:string}>}>({queryKey:["form-assignments",template.id],queryFn:()=>api(`/form-templates/${template.id}/assignments/`),enabled:template.approval_status==="APPROVED"});
  const preview=useQuery<{providers:Array<{provider_id:number;provider_name:string;mismatch:boolean;duplicate:boolean;can_assign:boolean}>;summary:{assignable:number;mismatches:number;duplicates:number}}>({
    queryKey:["assignment-preview",template.id,mode,selected,periodId,overrideReason],
    queryFn:()=>api(`/form-templates/${template.id}/assignment-preview/?mode=${mode}&provider_ids=${selected.join(",")}${periodId?`&period=${periodId}`:""}&override_reason=${encodeURIComponent(overrideReason)}`),enabled:selected.length>0,
  });
  const send=useMutation<{delivery_type:"IMMEDIATE"|"SCHEDULED";obligations_created:number;recurring_schedules_created:number;duplicates:number}>({mutationFn:()=>api(`/form-templates/${template.id}/assignments/`,{method:"POST",body:JSON.stringify({mode,provider_ids:selected,period_id:mode==="MANUAL"?Number(periodId):undefined,effective_from:effectiveFrom,effective_to:effectiveTo||null,override_reason:overrideReason})}),onSuccess:(result)=>{toast(result.delivery_type==="IMMEDIATE"?(result.obligations_created?`${result.obligations_created} provider form${result.obligations_created===1?"":"s"} sent.`:"Already sent for the selected provider and period."):`${result.recurring_schedules_created} recurring schedule${result.recurring_schedules_created===1?"":"s"} configured. Forms will be created when matching future periods are activated.`,"success");setSelected([]);qc.invalidateQueries({queryKey:["form-assignments",template.id]});qc.invalidateQueries({queryKey:["expected-submissions"]});},onError:(error:Error)=>toast(error.message,"error")});
  if(template.approval_status!=="APPROVED")return <section className="rounded-xl border bg-white p-5"><h2 className="font-semibold">Assignments</h2><p className="mt-1 text-sm text-[#737780]">Publish this template before sending it to providers.</p></section>;
  const providerList=providers.data?.results??[];
  return <><section className="rounded-xl border bg-white p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">Send to providers</h2><p className="mt-1 text-xs text-[#737780]">Use the primary action to deliver this exact version immediately for one active reporting period.</p></div><button type="button" onClick={()=>setSendOpen(true)} className="rounded-lg bg-[#0066cc] px-4 py-2 text-sm font-semibold text-white">Send for one period</button></div>
    <div className="mt-4 grid gap-3 sm:grid-cols-3"><select className={inp} value={mode} onChange={e=>setMode(e.target.value as "RECURRING"|"MANUAL")}><option value="MANUAL">Send for one active period</option><option value="RECURRING">Configure recurring schedule</option></select>{mode==="MANUAL"?<select className={`${inp} sm:col-span-2`} value={periodId} onChange={e=>setPeriodId(e.target.value)}><option value="">Select active reporting period</option>{(periods.data?.results??[]).filter(p=>p.status==="ACTIVE").map(p=><option key={p.id} value={p.id}>{p.name} · {p.status}</option>)}</select>:<><input className={inp} type="date" value={effectiveFrom} onChange={e=>setEffectiveFrom(e.target.value)}/><input className={inp} type="date" value={effectiveTo} onChange={e=>setEffectiveTo(e.target.value)} aria-label="Recurring assignment end date"/></>}</div>
    {mode==="RECURRING"&&<p className="mt-3 rounded-lg bg-[#f7f9fb] px-3 py-2 text-xs text-[#43474f]">This creates a schedule only. Provider forms and notifications are generated when matching future reporting periods are activated.</p>}
    <div className="mt-4 max-h-56 overflow-y-auto rounded-lg border p-2">{providerList.map(provider=>{const mismatch=provider.sector!==template.sector||provider.category!==template.provider_category;return <label key={provider.id} className="flex items-center gap-3 rounded px-2 py-2 hover:bg-[#f7f9fb]"><input type="checkbox" checked={selected.includes(provider.id)} onChange={()=>setSelected(items=>items.includes(provider.id)?items.filter(id=>id!==provider.id):[...items,provider.id])}/><span className="flex-1 text-sm">{provider.registered_name}</span>{mismatch&&<span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] text-amber-800">Type mismatch</span>}</label>})}</div>
    {(preview.data?.summary.mismatches??0)>0&&<textarea className={`${inp} mt-3`} rows={2} placeholder="Required reason for assigning across a sector or provider-type mismatch" value={overrideReason} onChange={e=>setOverrideReason(e.target.value)}/>}
    {preview.data&&<p className="mt-3 text-xs text-[#43474f]">{preview.data.summary.assignable} assignable · {preview.data.summary.duplicates} already assigned · {preview.data.summary.mismatches} mismatches</p>}
    <div className="mt-3 flex justify-end"><button onClick={()=>send.mutate()} disabled={!selected.length||send.isPending||(mode==="MANUAL"&&!periodId)||(Boolean(preview.data?.summary.mismatches)&&!overrideReason.trim())} className="rounded-lg bg-[#001836] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{mode==="MANUAL"?"Confirm & send":"Configure recurring schedule"}</button></div>
    {(assignments.data?.recurring.length||assignments.data?.manual.length)?<div className="mt-5 border-t pt-4 text-xs text-[#43474f]"><p className="font-semibold">Current assignments</p>{assignments.data?.recurring.map(a=><p key={`r${a.id}`} className="mt-1">Recurring · {a.provider_name} · from {a.effective_from}{a.effective_to?` to ${a.effective_to}`:""}</p>)}{assignments.data?.manual.map(a=><p key={`m${a.id}`} className="mt-1">Manual · {a.provider_name} · {a.period_name}</p>)}</div>:null}
  </section><FormSendDialog template={template} open={sendOpen} onClose={()=>setSendOpen(false)}/></>;
}

function AddFieldForm({ templateId, sectionId, headings, availableFields, onDone }: { templateId: string; sectionId: number; headings: FormHeading[]; availableFields: FormField[]; onDone: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const initial = { field_code:"", label:"", field_type:"text" as FieldType, unit:"", is_required:false, help_text:"", formula:"", heading:"", conditional_on_field:"", conditional_on_value:"", options:"" };
  const [d, setD] = useState(initial);

  const mut = useMutation({
    mutationFn: async () => {
      const { options, conditional_on_field, heading, ...fieldData } = d;
      const field = await api<FormField>(`/form-templates/${templateId}/sections/${sectionId}/fields/`, {
        method:"POST",
        body: JSON.stringify({ ...fieldData, heading: heading ? Number(heading) : null, conditional_on_field: conditional_on_field ? Number(conditional_on_field) : null }),
      });
      if (["select", "multiselect"].includes(d.field_type)) {
        const labels = options.split("\n").map((item) => item.trim()).filter(Boolean);
        for (const label of labels) {
          await api(`/fields/${field.id}/options/`, { method:"POST", body:JSON.stringify({ value:label, label }) });
        }
      }
      return field;
    },
    onSuccess: () => {
      toast("Field added.", "success");
      qc.invalidateQueries({ queryKey: ["form-template", templateId] });
       setD(initial);
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
        {["select", "multiselect"].includes(d.field_type) && <div className="sm:col-span-3">
          <label className={lbl}>Options (one per line)</label>
          <textarea className={inp} rows={4} value={d.options} onChange={e=>setD(p=>({...p,options:e.target.value}))} />
        </div>}
        {d.field_type === "formula" && <div className="sm:col-span-3">
          <label className={lbl}>Allow-listed formula expression</label>
          <input className={inp} placeholder="e.g. total_prepaid + total_postpaid" value={d.formula} onChange={e=>setD(p=>({...p,formula:e.target.value}))} />
        </div>}
        <div>
          <label className={lbl}>Conditional parent</label>
          <select className={inp} value={d.conditional_on_field} onChange={e=>setD(p=>({...p,conditional_on_field:e.target.value}))}>
            <option value="">Always visible</option>
            {availableFields.map(field=><option key={field.id} value={field.id}>{field.label}</option>)}
          </select>
        </div>
        <div>
          <label className={lbl}>Heading</label>
          <select className={inp} value={d.heading} onChange={e=>setD(p=>({...p,heading:e.target.value}))}>
            <option value="">No heading</option>
            {headings.map(heading=><option key={heading.id} value={heading.id}>{heading.title}</option>)}
          </select>
        </div>
        {d.conditional_on_field && <div className="sm:col-span-2">
          <label className={lbl}>Required parent value</label>
          <input className={inp} value={d.conditional_on_value} onChange={e=>setD(p=>({...p,conditional_on_value:e.target.value}))} />
        </div>}
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
  const [d, setD] = useState({ grid_code:"", title:"", row_mode:"REPEATABLE" as "FIXED"|"REPEATABLE", min_rows:0, instructions:"" });

  const mut = useMutation({
    mutationFn: () => api(`/form-templates/${templateId}/sections/${sectionId}/grids/`, {
      method:"POST", body: JSON.stringify(d)
    }),
    onSuccess: () => {
      toast("Grid added.", "success");
      qc.invalidateQueries({ queryKey: ["form-template", templateId] });
      setD({ grid_code:"", title:"", row_mode:"REPEATABLE", min_rows:0, instructions:"" });
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
        <div>
          <label className={lbl}>Minimum rows</label>
          <input className={inp} type="number" min={0} value={d.min_rows}
            onChange={e => setD(p => ({ ...p, min_rows: Number(e.target.value) }))} />
        </div>
        <div className="col-span-2">
          <label className={lbl}>Instructions</label>
          <input className={inp} value={d.instructions}
            onChange={e => setD(p => ({ ...p, instructions: e.target.value }))} />
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

function GridEditor({ grid, editable, onChanged }: { grid: FormGrid; editable: boolean; onChanged: () => void }) {
  const { toast } = useToast();
  const [column, setColumn] = useState({ column_code:"", label:"", field_type:"text" as FieldType, unit:"", is_required:true });
  const [rowLabel, setRowLabel] = useState("");
  const addColumn = useMutation({
    mutationFn: () => api(`/grids/${grid.id}/columns/`, { method:"POST", body:JSON.stringify(column) }),
    onSuccess: () => { setColumn({column_code:"",label:"",field_type:"text",unit:"",is_required:true}); onChanged(); },
    onError: (error:Error) => toast(error.message, "error"),
  });
  const addRow = useMutation({
    mutationFn: () => api(`/grids/${grid.id}/rows/`, { method:"POST", body:JSON.stringify({row_label:rowLabel}) }),
    onSuccess: () => { setRowLabel(""); onChanged(); },
    onError: (error:Error) => toast(error.message, "error"),
  });
  async function remove(path:string) {
    try { await api(path, {method:"DELETE"}); onChanged(); }
    catch (error) { toast(error instanceof Error ? error.message : "Unable to remove item.", "error"); }
  }
  return <div className="mb-2 rounded-[8px] border border-[#c3c6d0] bg-[#f7f9fb] p-3">
    <div className="flex items-center gap-2"><span className="flex-1 text-[12px] font-semibold">{grid.title}</span><span className="text-[10px] text-[#737780]">{grid.row_mode} · min {grid.min_rows}</span></div>
    {grid.instructions && <p className="mt-1 text-[10px] text-[#737780]">{grid.instructions}</p>}
    <div className="mt-2 flex flex-wrap gap-1">{grid.columns.map(item => <span key={item.id} className="inline-flex items-center gap-1 rounded border bg-white px-2 py-1 text-[10px]">{item.label} ({item.field_type}{item.unit ? `, ${item.unit}`:""}){editable && <button aria-label={`Delete ${item.label}`} onClick={() => remove(`/grids/${grid.id}/columns/${item.id}/`)}><Trash2 size={10}/></button>}</span>)}</div>
    {grid.row_mode === "FIXED" && <div className="mt-2 flex flex-wrap gap-1">{grid.fixed_rows?.map(row => <span key={row.id} className="inline-flex items-center gap-1 rounded border bg-white px-2 py-1 text-[10px]">{row.row_label}{editable && <button aria-label={`Delete ${row.row_label}`} onClick={() => remove(`/grids/${grid.id}/rows/${row.id}/`)}><Trash2 size={10}/></button>}</span>)}</div>}
    {editable && <div className="mt-3 space-y-2 border-t border-[#dce3e9] pt-3">
      <div className="grid gap-2 sm:grid-cols-5">
        <input className={inp} placeholder="Column code" value={column.column_code} onChange={e=>setColumn(p=>({...p,column_code:e.target.value}))}/>
        <input className={inp} placeholder="Label" value={column.label} onChange={e=>setColumn(p=>({...p,label:e.target.value}))}/>
        <select className={inp} value={column.field_type} onChange={e=>setColumn(p=>({...p,field_type:e.target.value as FieldType}))}>{FIELD_TYPES.filter(item=>!["formula","declaration"].includes(item.value)).map(item=><option key={item.value} value={item.value}>{item.label}</option>)}</select>
        <input className={inp} placeholder="Unit" value={column.unit} onChange={e=>setColumn(p=>({...p,unit:e.target.value}))}/>
        <button className="rounded bg-[#002d5b] px-3 text-xs font-semibold text-white disabled:opacity-50" disabled={!column.column_code||!column.label||addColumn.isPending} onClick={()=>addColumn.mutate()}>Add column</button>
      </div>
      {grid.row_mode === "FIXED" && <div className="flex gap-2"><input className={inp} placeholder="Fixed row label" value={rowLabel} onChange={e=>setRowLabel(e.target.value)}/><button className="shrink-0 rounded border px-3 text-xs font-semibold disabled:opacity-50" disabled={!rowLabel||addRow.isPending} onClick={()=>addRow.mutate()}>Add fixed row</button></div>}
    </div>}
  </div>;
}

function ValidationRuleEditor({ templateId, sections, editable }: { templateId:string; sections:FormSection[]; editable:boolean }) {
  type Rule = {id:number;rule_type:string;severity:string;field:number|null;grid:number|null;message:string;parameters:Record<string,unknown>};
  const { toast } = useToast();
  const qc = useQueryClient();
  const query = useQuery<Rule[]>({queryKey:["validation-rules",templateId],queryFn:async()=>{const response=await api<Rule[]|{results:Rule[]}>(`/form-templates/${templateId}/validation-rules/`);return Array.isArray(response)?response:response.results;}});
  const fields = sections.flatMap(section=>section.fields);
  const grids = sections.flatMap(section=>section.grids);
  const [rule,setRule]=useState({rule_type:"RANGE",severity:"BLOCK",target:"",message:"",parameters:'{"min": 0}'});
  const create = useMutation({mutationFn:()=>{
    const [kind,id]=rule.target.split(":");
    return api(`/form-templates/${templateId}/validation-rules/`,{method:"POST",body:JSON.stringify({rule_type:rule.rule_type,severity:rule.severity,field:kind==="field"?Number(id):null,grid:kind==="grid"?Number(id):null,message:rule.message,parameters:JSON.parse(rule.parameters)})});
  },onSuccess:()=>{toast("Validation rule added.","success");qc.invalidateQueries({queryKey:["validation-rules",templateId]});},onError:(error:Error)=>toast(error.message,"error")});
  return <section className="rounded-[12px] border border-[#eceef0] bg-white p-4">
    <h2 className="text-sm font-semibold">Validation rules</h2><p className="mt-1 text-xs text-[#737780]">Rules use a validated JSON parameter schema; executable code is never accepted.</p>
    <div className="mt-3 space-y-2">{query.data?.map(item=><div key={item.id} className="rounded border bg-[#f7f9fb] px-3 py-2 text-xs"><span className="font-semibold">{item.rule_type} · {item.severity}</span> — {item.message}<pre className="mt-1 overflow-auto text-[10px]">{JSON.stringify(item.parameters)}</pre></div>)}</div>
    {editable&&<div className="mt-4 grid gap-2 border-t pt-4 sm:grid-cols-2">
      <select className={inp} value={rule.rule_type} onChange={e=>setRule(p=>({...p,rule_type:e.target.value}))}>{["TYPE","RANGE","OPTION","DATE","COORDINATE","CONDITIONAL","FORMULA","COMPARISON","GRID_TOTAL"].map(type=><option key={type}>{type}</option>)}</select>
      <select className={inp} value={rule.severity} onChange={e=>setRule(p=>({...p,severity:e.target.value}))}><option value="BLOCK">Blocking</option><option value="WARN">Warning</option></select>
      <select className={inp} value={rule.target} onChange={e=>setRule(p=>({...p,target:e.target.value}))}><option value="">Select target</option>{fields.map(field=><option key={`f${field.id}`} value={`field:${field.id}`}>Field: {field.label}</option>)}{grids.map(grid=><option key={`g${grid.id}`} value={`grid:${grid.id}`}>Grid: {grid.title}</option>)}</select>
      <input className={inp} placeholder="User-facing message" value={rule.message} onChange={e=>setRule(p=>({...p,message:e.target.value}))}/>
      <textarea className={`${inp} sm:col-span-2 font-mono`} rows={3} aria-label="Rule parameters JSON" value={rule.parameters} onChange={e=>setRule(p=>({...p,parameters:e.target.value}))}/>
      <button className="rounded bg-[#002d5b] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50" disabled={!rule.target||!rule.message||create.isPending} onClick={()=>create.mutate()}>Add validated rule</button>
    </div>}
  </section>;
}

function SectionBlock({ section, templateId, editable }: { section: FormSection; templateId: string; editable: boolean }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [addingHeading, setAddingHeading] = useState(false);
  const [addingField, setAddingField] = useState(false);
  const [addingGrid, setAddingGrid] = useState(false);
  const [headingDraft, setHeadingDraft] = useState({ heading_code:"", title:"", level:1 as 1|2|3 });

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

  const addHeadingMut = useMutation({
    mutationFn:()=>api(`/form-templates/${templateId}/sections/${section.id}/headings/`,{method:"POST",body:JSON.stringify(headingDraft)}),
    onSuccess:()=>{toast("Heading added.","success");setHeadingDraft({heading_code:"",title:"",level:1});setAddingHeading(false);qc.invalidateQueries({queryKey:["form-template",templateId]});},
    onError:(error:Error)=>toast(error.message,"error"),
  });

  async function updateHeading(heading:FormHeading, changes:Partial<FormHeading>) {
    try {
      await api(`/form-templates/${templateId}/sections/${section.id}/headings/${heading.id}/`,{method:"PATCH",body:JSON.stringify(changes)});
      qc.invalidateQueries({queryKey:["form-template",templateId]});
    } catch (error) { toast(error instanceof Error?error.message:"Unable to update heading.","error"); }
  }

  async function deleteHeading(heading:FormHeading) {
    try {
      await api(`/form-templates/${templateId}/sections/${section.id}/headings/${heading.id}/`,{method:"DELETE"});
      qc.invalidateQueries({queryKey:["form-template",templateId]});
    } catch (error) { toast(error instanceof Error?error.message:"Unable to remove heading.","error"); }
  }

  const structureItems = [
    ...(section.headings??[]).map(heading=>({kind:"heading" as const,sortOrder:heading.sort_order,heading})),
    ...section.fields.map(field=>({kind:"field" as const,sortOrder:field.sort_order,field})),
  ].sort((left,right)=>left.sortOrder-right.sortOrder);

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
        {editable && <button onClick={e => { e.stopPropagation(); if (confirm(`Delete section "${section.title}"?`)) deleteSectionMut.mutate(); }}
          className="ml-2 text-[#737780] hover:text-[#e31937] transition-colors">
          <Trash2 size={14} />
        </button>}
      </div>

      {open && (
        <div className="border-t border-[#eceef0] px-5 pb-4 pt-3 space-y-2">
          {section.instructions && (
            <p className="text-[12px] text-[#43474f] italic mb-3">{section.instructions}</p>
          )}

          {/* Ordered headings and fields */}
          {structureItems.length > 0 && (
            <div className="space-y-1 mb-3">
              {structureItems.map(item => item.kind === "heading" ? (
                <div key={`h${item.heading.id}`} className={`flex items-center gap-2 rounded-[8px] border-l-4 px-3 py-2 ${item.heading.level===1?'border-[#001836] bg-[#e8f1fb]':item.heading.level===2?'border-[#0066cc] bg-[#f1f7fd]':'border-[#8aa9c7] bg-[#f7f9fb]'}`}>
                  <span className="text-[10px] font-semibold uppercase text-[#737780]">Header {item.heading.level}</span>
                  {editable ? <input defaultValue={item.heading.title} onBlur={event=>{if(event.target.value.trim()&&event.target.value.trim()!==item.heading.title)updateHeading(item.heading,{title:event.target.value.trim()});}} className="min-w-0 flex-1 border-0 bg-transparent text-[12px] font-semibold outline-none"/> : <span className="flex-1 text-[12px] font-semibold">{item.heading.title}</span>}
                  {editable&&<><label className="flex items-center gap-1 text-[10px] text-[#737780]">Order<input aria-label={`Order for ${item.heading.title}`} type="number" min={0} defaultValue={item.heading.sort_order} onBlur={event=>{const next=Number(event.target.value);if(Number.isFinite(next)&&next!==item.heading.sort_order)updateHeading(item.heading,{sort_order:next});}} className="w-14 rounded border bg-white px-1 py-0.5"/></label><select aria-label={`Level for ${item.heading.title}`} value={item.heading.level} onChange={event=>updateHeading(item.heading,{level:Number(event.target.value) as 1|2|3})} className="rounded border bg-white px-1 py-0.5 text-[10px]"><option value={1}>Level 1</option><option value={2}>Level 2</option><option value={3}>Level 3</option></select><button aria-label={`Delete ${item.heading.title}`} onClick={()=>{if(confirm(`Remove heading "${item.heading.title}"? Fields remain in the section.`))deleteHeading(item.heading);}} className="text-[#737780] hover:text-[#e31937]"><Trash2 size={12}/></button></>}
                </div>
              ) : (
                <div key={`f${item.field.id}`} className="flex items-center gap-3 rounded-[8px] bg-[#f7f9fb] px-3 py-2">
                  <span className="text-[12px] font-medium text-[#191c1e] flex-1">{item.field.label}</span>
                  <span className="text-[10px] font-mono text-[#737780] bg-white border border-[#eceef0] rounded px-1.5 py-0.5">{item.field.field_type}</span>
                  {item.field.unit&&<span className="text-[10px] text-[#737780]">{item.field.unit}</span>}
                  {item.field.is_required&&<span className="text-[10px] text-[#e31937]">*</span>}
                  {editable&&<button onClick={()=>{if(confirm(`Remove field "${item.field.label}"?`))deleteFieldMut.mutate(item.field.id);}} className="text-[#c3c6d0] hover:text-[#e31937] transition-colors ml-1"><Trash2 size={12}/></button>}
                </div>
              ))}
            </div>
          )}

          {/* Grids list */}
          {section.grids?.map(grid => <GridEditor key={grid.id} grid={grid} editable={editable}
            onChanged={() => qc.invalidateQueries({queryKey:["form-template", templateId]})} />)}

          {/* Add heading / field / grid buttons */}
          {editable && !addingHeading && !addingField && !addingGrid && (
            <div className="flex gap-2 pt-1">
              <button onClick={() => setAddingHeading(true)}
                className="flex items-center gap-1.5 rounded-[8px] border border-[#c3c6d0] px-3 py-1.5 text-[12px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors">
                <Plus size={12} /> Add Heading
              </button>
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

          {addingHeading&&<div className="mt-3 grid gap-2 rounded-[10px] border bg-[#f7f9fb] p-4 sm:grid-cols-[1fr_2fr_120px_auto]"><input className={inp} placeholder="Heading code" value={headingDraft.heading_code} onChange={e=>setHeadingDraft(current=>({...current,heading_code:e.target.value}))}/><input className={inp} placeholder="Heading title" value={headingDraft.title} onChange={e=>setHeadingDraft(current=>({...current,title:e.target.value}))}/><select className={inp} value={headingDraft.level} onChange={e=>setHeadingDraft(current=>({...current,level:Number(e.target.value) as 1|2|3}))}><option value={1}>Level 1</option><option value={2}>Level 2</option><option value={3}>Level 3</option></select><div className="flex gap-2"><button disabled={!headingDraft.heading_code||!headingDraft.title||addHeadingMut.isPending} onClick={()=>addHeadingMut.mutate()} className="rounded bg-[#001836] px-3 text-xs font-semibold text-white disabled:opacity-50">Add</button><button onClick={()=>setAddingHeading(false)} className="rounded border px-3 text-xs">Cancel</button></div></div>}
          {addingField && <AddFieldForm templateId={templateId} sectionId={section.id} headings={section.headings??[]} availableFields={section.fields} onDone={() => setAddingField(false)} />}
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
  const [activeTab, setActiveTab] = useState<"structure"|"workbook"|"validation"|"assignments"|"gaps"|"publication">("structure");
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

  const sourceMut = useMutation({
    mutationFn: (data: {source_reference: string; source_sha256: string}) => api.patch(`/form-templates/${id}/`, { ...data, mapping_complete: true }),
    onSuccess: () => { toast("Source map recorded.", "success"); qc.invalidateQueries({ queryKey: ["form-template", id] }); },
    onError: (error: Error) => toast(error.message, "error"),
  });
  const approveMut = useMutation({
    mutationFn: () => api.post(`/form-templates/${id}/approve/`, {}),
    onSuccess: () => { toast("Form version approved and published.", "success"); qc.invalidateQueries({ queryKey: ["form-template", id] }); },
    onError: (error: Error) => toast(error.message, "error"),
  });
  const cloneMut = useMutation({
    mutationFn: (version: string) => api.post(`/form-templates/${id}/clone/`, { version }),
    onSuccess: () => toast("Draft version cloned.", "success"),
    onError: (error: Error) => toast(error.message, "error"),
  });

  function captureSource() {
    const source_reference = window.prompt("Approved source reference");
    if (!source_reference?.trim()) return;
    const source_sha256 = window.prompt("Source file SHA-256 (64 hexadecimal characters)");
    if (!source_sha256 || !/^[a-fA-F0-9]{64}$/.test(source_sha256)) { toast("Enter a valid SHA-256 hash.", "error"); return; }
    sourceMut.mutate({ source_reference: source_reference.trim(), source_sha256: source_sha256.toLowerCase() });
  }

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
      <Link href="/forms"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
        ← Back to Form Templates
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-mono font-semibold text-[#0066cc] mb-1">{template.form_code}</p>
          <h1 className="text-[26px] font-semibold text-[#191c1e]">{template.name}</h1>
          <p className="text-[13px] text-[#43474f] mt-0.5">
            {template.sector} /{" "}
            {template.provider_category} · {template.frequency} · v{template.version}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          {template.approval_status !== "APPROVED" && <button onClick={captureSource}
            className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[12px] font-semibold text-[#43474f]">Source Map</button>}
          {template.approval_status !== "APPROVED" && template.mapping_complete && (
            <button onClick={() => approveMut.mutate()}
              className="rounded-[8px] bg-[#1f7a4d] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#175f3b]">
              Approve & Publish
            </button>
          )}
          {template.approval_status === "APPROVED" && (
            <span className="rounded-full bg-[#e5f4eb] px-3 py-1.5 text-[12px] font-semibold text-[#1f7a4d]">● Active</span>
          )}
        </div>
      </div>

      <div role="tablist" aria-label="Form Builder sections" className="flex gap-1 overflow-x-auto rounded-xl border border-[#eceef0] bg-white p-1">
        {([['structure','Structure'],['workbook','Workbook Import'],['validation','Validation'],['assignments','Assignments'],['gaps','Gap Analysis'],['publication','Publication']] as const).map(([value,label])=><button key={value} role="tab" aria-selected={activeTab===value} onClick={()=>setActiveTab(value)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold ${activeTab===value?'bg-[#001836] text-white':'text-[#43474f] hover:bg-[#f2f4f6]'}`}>{label}</button>)}
      </div>

      {activeTab==="publication"&&<div className="rounded-[12px] border border-[#eceef0] bg-white p-4 text-[12px] text-[#43474f]">
        <p className="mb-3 rounded-lg bg-[#f2f4f6] p-3"><span className="font-semibold">Publication basis:</span> {template.mapping_basis==="PRD_SECTION_11"?"PRD Section 11 — blocker/high gaps must pass.":template.mapping_basis==="CUSTOM"?"Custom NCA form — Section 11 matching is not applicable.":"Approved source form — Section 11 matching is not applicable."}</p>
        <p><span className="font-semibold">Source:</span> {template.source_reference || "Not recorded"}</p>
        <p className="mt-1 break-all font-mono text-[10px] text-[#737780]">{template.source_sha256 || "No source hash"}</p>
        <button onClick={() => { const version=window.prompt("New version number"); if(version?.trim()) cloneMut.mutate(version.trim()); }}
          className="mt-3 rounded-[8px] border border-[#c3c6d0] px-3 py-1.5 text-[11px] font-semibold">Clone as new immutable version</button>
        <a href={`/forms/${id}/gaps`} className="ml-2 inline-flex rounded-[8px] bg-[#0066cc] px-3 py-1.5 text-[11px] font-semibold text-white">Gap Analysis</a>
      </div>}

      {activeTab==="workbook"&&<div className="rounded-[12px] border border-[#eceef0] bg-white p-5 text-sm text-[#43474f]"><h2 className="font-semibold text-[#191c1e]">Workbook provenance</h2><p className="mt-2">{template.source_reference||"This version was created manually and has no workbook source."}</p><p className="mt-2 break-all font-mono text-xs text-[#737780]">{template.source_sha256||"No workbook SHA-256 recorded"}</p><Link href="/forms" className="mt-4 inline-flex rounded-lg bg-[#001836] px-4 py-2 text-xs font-semibold text-white">Import a workbook as a new draft</Link></div>}

      {activeTab==="gaps"&&<div className="rounded-[12px] border border-[#eceef0] bg-white p-5"><h2 className="text-sm font-semibold">Gap Analysis</h2><p className="mt-1 text-xs text-[#737780]">{template.mapping_basis==="PRD_SECTION_11"?"Review objective Section 11 requirements and publication blockers for this immutable version.":"Section 11 matching is not applicable to this custom/source-derived form. Publication uses its configured structure, validation and source approval checks."}</p>{template.mapping_basis==="PRD_SECTION_11"&&<Link href={`/forms/${id}/gaps`} className="mt-4 inline-flex rounded-lg bg-[#0066cc] px-4 py-2 text-xs font-semibold text-white">Open Gap Analysis</Link>}</div>}

      {/* Section count */}
      <div className={activeTab==="structure"?"contents":"hidden"}>
      <div className="flex items-center justify-between">
        <p className="text-[14px] text-[#43474f]">
          <span className="font-semibold text-[#191c1e]">{sections.length}</span> section{sections.length !== 1 ? "s" : ""}
        </p>
        {template.approval_status !== "APPROVED" && <button onClick={() => setAddingSection(v => !v)}
          className="flex items-center gap-1.5 rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b]">
          <Plus size={14} /> {addingSection ? "Cancel" : "Add Section"}
        </button>}
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
                <SectionBlock section={s} templateId={id} editable={template.approval_status !== "APPROVED"} />
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
      {activeTab==="validation"&&<ValidationRuleEditor templateId={id} sections={sections as FormSection[]} editable={template.approval_status !== "APPROVED"} />}
      {activeTab==="assignments"&&<AssignmentPanel template={template} />}
    </div>
  );
}

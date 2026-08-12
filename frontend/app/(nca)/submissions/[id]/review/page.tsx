"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Clock, FileWarning, MessageSquare, ShieldCheck, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { WorkflowBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime } from "@/lib/utils";
import type { FieldStatus, FormSection, FormTemplate, User, WorkflowStatus } from "@/lib/types";

interface SubmissionSummary {
  id: number; version: number; completion_pct: string; workflow_status: WorkflowStatus;
  form_code: string; form_name: string; period_name: string; provider_name: string;
  submitted_at: string | null; reviewed_at: string | null; kmz_required: boolean;
  form_template_id: number; form_version: string; mapping_basis: string; source_reference: string;
}
interface ValueItem {
  id: number; field: number | null; grid: number | null; grid_row_id: string; grid_column: number | null;
  value: string; value_status: FieldStatus; explanation: string;
  non_filled_disposition: "ACCEPTED" | "REJECTED" | null; disposition_note: string;
}
interface RequirementItem {
  id: number; requirement_key: string; requirement_label: string; requirement_description: string;
  requirement_type: string; severity: string; status: "MATCHED" | "MISSING" | "PARTIAL" | "NOT_APPLICABLE"; evidence: string;
}
interface ReviewData {
  submission: SubmissionSummary;
  template: FormTemplate & { sections: FormSection[] };
  values: ValueItem[];
  requirements: RequirementItem[];
  uploads: Array<{ id:number; requirement:number; category:string; file_name:string; file_size:number; sha256:string; scan_status:string; review_status:string; review_note:string; uploaded_at:string }>;
  validation: null | { id:number; status:string; scope:string; completed_at:string; results:Array<{id:number;severity:string;target_type:string;target_id:string;code:string;message:string}> };
  approval_blockers: Array<{code:string;type:string;id:string|number;section_code:string;label:string}>;
  correction_items: Array<{id:number;target_type:string;target_id:string;instruction:string;status:string}>;
  legacy_warning: null | { title:string; message:string; missing_requirement_count:number };
}
interface ReviewAction { id:number; action:string; comment:string; target_type:string; target_id:string; is_provider_visible:boolean; created_by_name:string; created_at:string }

const nonFilled = new Set(["NOT_APPLICABLE", "NOT_AVAILABLE", "NOT_REQUIRED"]);
const badge:Record<string,string> = {
  MATCHED:"bg-green-100 text-green-800", MISSING:"bg-red-100 text-red-800", PARTIAL:"bg-amber-100 text-amber-800",
  BLOCK:"bg-red-100 text-red-800", WARN:"bg-amber-100 text-amber-800", PASS:"bg-green-100 text-green-800", FAIL:"bg-red-100 text-red-800",
};

function ValueDisplay({ value, unit }: { value?:ValueItem; unit?:string }) {
  if (!value) return <span className="text-red-700">Missing</span>;
  const shown = value.value_status === "PROVIDED" || value.value_status === "SYSTEM_CALCULATED" ? value.value || "—" : value.value_status.replaceAll("_", " ");
  return <div><p className={value.value_status === "MISSING" ? "font-semibold text-red-700" : "font-medium text-[#191c1e]"}>{shown}{unit && value.value ? ` ${unit}` : ""}</p>{value.explanation&&<p className="mt-1 text-xs italic text-[#737780]">{value.explanation}</p>}{value.non_filled_disposition&&<p className="mt-1 text-xs text-[#737780]">Disposition: {value.non_filled_disposition}{value.disposition_note?` — ${value.disposition_note}`:""}</p>}</div>;
}

function SectionPanel({ section, data, canReview, selected, toggle, refresh }: { section:FormSection; data:ReviewData; canReview:boolean; selected:Set<string>; toggle:(key:string)=>void; refresh:()=>void }) {
  const [open,setOpen]=useState(true);
  const valuesByField = useMemo(()=>new Map(data.values.filter(v=>v.field).map(v=>[v.field!,v])),[data.values]);
  const gridValues = data.values.filter(v=>v.grid);
  const requirements = data.requirements.filter(r=>r.requirement_key.includes(`:${section.section_code}`));
  const missing = requirements.filter(r=>r.status!=="MATCHED").length;
  async function disposition(value:ValueItem, decision:"ACCEPTED"|"REJECTED") {
    const note=decision==="REJECTED"?window.prompt("Why is this explanation rejected?"):"Accepted during regulatory review.";
    if(decision==="REJECTED"&&!note?.trim()) return;
    await api.post(`/submissions/${data.submission.id}/values/${value.id}/non-filled-disposition/`,{decision,note});refresh();
  }
  return <section className="overflow-hidden rounded-2xl border bg-white">
    <button onClick={()=>setOpen(x=>!x)} className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-[#f7f9fb]">
      {open?<ChevronDown size={16}/>:<ChevronRight size={16}/>}<div className="flex-1"><h3 className="font-semibold">{section.title}</h3><p className="text-xs text-[#737780]">{section.instructions}</p></div>
      {missing>0&&<span className="rounded-full bg-red-100 px-2 py-1 text-xs font-semibold text-red-800">{missing} PRD gap{missing===1?"":"s"}</span>}
      {canReview&&<label onClick={e=>e.stopPropagation()} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={selected.has(`SECTION:${section.section_code}`)} onChange={()=>toggle(`SECTION:${section.section_code}`)}/> Correct section</label>}
    </button>
    {open&&<div className="space-y-5 border-t p-5">
      {section.fields.length>0&&<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-[#f7f9fb] text-xs uppercase text-[#737780]"><tr><th className="p-3">Field</th><th className="p-3">Reported value</th>{canReview&&<th className="p-3">Correction</th>}</tr></thead><tbody className="divide-y">{section.fields.map(field=>{const value=valuesByField.get(field.id);return <tr key={field.id}><td className="p-3"><p className="font-medium">{field.label}</p><p className="text-xs text-[#737780]">{field.field_type}{field.unit?` · ${field.unit}`:""}{field.is_required?" · Required":" · Optional"}</p>{field.help_text&&<p className="mt-1 max-w-xl text-xs text-[#737780]">{field.help_text}</p>}</td><td className="p-3"><ValueDisplay value={value} unit={field.unit}/>{value&&nonFilled.has(value.value_status)&&canReview&&<div className="mt-2 flex gap-2"><button onClick={()=>disposition(value,"ACCEPTED")} className="rounded border border-green-700 px-2 py-1 text-xs text-green-700">Accept</button><button onClick={()=>disposition(value,"REJECTED")} className="rounded border border-red-700 px-2 py-1 text-xs text-red-700">Reject</button></div>}</td>{canReview&&<td className="p-3"><input aria-label={`Request correction for ${field.label}`} type="checkbox" checked={selected.has(`FIELD:${field.id}`)} onChange={()=>toggle(`FIELD:${field.id}`)}/></td>}</tr>})}</tbody></table></div>}
      {section.grids.map(grid=>{
        const cells=gridValues.filter(v=>v.grid===grid.id);const rowIds=grid.row_mode==="FIXED"?(grid.fixed_rows??[]).map(r=>String(r.id)):Array.from(new Set(cells.map(v=>v.grid_row_id)));
        const rowLabel=(id:string)=>grid.row_mode==="FIXED"?(grid.fixed_rows??[]).find(r=>String(r.id)===id)?.row_label??id:id;
        return <div key={grid.id}><div className="mb-2 flex items-end justify-between"><div><h4 className="font-semibold">{grid.title}</h4><p className="text-xs text-[#737780]">{grid.row_mode==="FIXED"?`${rowIds.length} prescribed rows`:`${rowIds.length} reported row(s); minimum ${grid.min_rows}`}</p></div></div>
          <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-[#f7f9fb] text-xs uppercase text-[#737780]"><tr><th className="p-3">Row</th>{grid.columns.map(c=><th key={c.id} className="p-3">{c.label}{c.unit&&<span className="block normal-case">{c.unit}</span>}</th>)}</tr></thead><tbody className="divide-y">{rowIds.length===0?<tr><td colSpan={grid.columns.length+1} className="p-5 text-center text-sm text-red-700">No rows were provided.</td></tr>:rowIds.map(row=><tr key={row}><td className="p-3 font-medium">{rowLabel(row)}</td>{grid.columns.map(column=>{const value=cells.find(v=>v.grid_row_id===row&&v.grid_column===column.id);const key=`GRID_CELL:${grid.id}:${row}:${column.id}`;return <td key={column.id} className="p-3"><ValueDisplay value={value} unit={column.unit}/>{canReview&&<label className="mt-2 flex items-center gap-1 text-xs text-[#737780]"><input type="checkbox" checked={selected.has(key)} onChange={()=>toggle(key)}/> Correct</label>}</td>})}</tr>)}</tbody></table></div>
        </div>})}
      {section.kmz_requirements.length>0&&<div><h4 className="font-semibold">Required uploads</h4>{section.kmz_requirements.map(req=>{const upload=data.uploads.find(x=>x.requirement===req.id);return <div key={req.id} className="mt-2 rounded-xl border p-4 text-sm"><p className="font-medium">{req.category}: {req.description}</p><p className="mt-1 text-[#737780]">{upload?`${upload.file_name} · Scan ${upload.scan_status} · Review ${upload.review_status}`:"No file uploaded"}</p></div>})}</div>}
    </div>}
  </section>;
}

export default function ReviewPage(){
  const id=Number(useParams<{id:string}>().id);const qc=useQueryClient();
  const [tab,setTab]=useState<"data"|"requirements"|"actions">("data");const [action,setAction]=useState<"approve"|"reject"|"correction"|"note"|null>(null);const [comment,setComment]=useState("");const [selected,setSelected]=useState<Set<string>>(new Set());const [error,setError]=useState("");
  const me=useQuery<User>({queryKey:["me"],queryFn:()=>api.get("/auth/me/")});
  const review=useQuery<ReviewData>({queryKey:["submission-review-data",id],queryFn:()=>api.get(`/submissions/${id}/review-data/`)});
  const history=useQuery<ReviewAction[]>({queryKey:["review-history",id],queryFn:()=>api.get(`/submissions/${id}/review/history/`)});
  const refresh=()=>{qc.invalidateQueries({queryKey:["submission-review-data",id]});qc.invalidateQueries({queryKey:["review-history",id]})};
  const mutation=useMutation({mutationFn:async()=>{
    if(!review.data) return;if(action!=="approve"&&!comment.trim()) throw new Error("A comment is required.");
    const urls={approve:`/submissions/${id}/review/approve/`,reject:`/submissions/${id}/review/reject/`,correction:`/submissions/${id}/review/request-correction/`,note:`/submissions/${id}/review/add-note/`};
    const targets=Array.from(selected).map(key=>{const [type,...parts]=key.split(":");return {type,id:parts.join(":"),comment};});
    return api.post(urls[action!],{comment,targets});
  },onSuccess:()=>{setAction(null);setComment("");setSelected(new Set());setError("");refresh()},onError:e=>setError(e instanceof ApiError?e.message:e instanceof Error?e.message:"Action failed.")});
  const start=useMutation({mutationFn:()=>api.post(`/submissions/${id}/review/start/`,{}),onSuccess:refresh,onError:e=>setError(e instanceof Error?e.message:"Review could not start.")});
  if(review.isLoading)return <div className="space-y-4">{[1,2,3].map(x=><Skeleton key={x} className="h-28 w-full"/>)}</div>;
  if(!review.data)return <div className="rounded-xl bg-red-50 p-5 text-red-700">Submission review data could not be loaded.</div>;
  const data=review.data,sub=data.submission,canReview=!!me.data?.capabilities.can_review_submissions,underReview=sub.workflow_status==="UNDER_REVIEW",canStart=["SUBMITTED","RESUBMITTED"].includes(sub.workflow_status);
  const toggle=(key:string)=>setSelected(prev=>{const next=new Set(prev);next.has(key)?next.delete(key):next.add(key);return next});
  return <div className="mx-auto max-w-[1280px] space-y-5">
    <a href="/submissions" className="text-sm font-semibold text-[#0066cc]">← Back to submissions</a>
    <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><p className="font-mono text-xs text-[#0066cc]">{sub.form_code} v{sub.form_version}</p><WorkflowBadge status={sub.workflow_status}/></div><h1 className="mt-1 text-2xl font-semibold">{sub.form_name}</h1><p className="text-sm text-[#737780]">{sub.provider_name} · {sub.period_name}</p></div><div className="grid grid-cols-2 gap-3 text-right text-xs"><div><p className="text-[#737780]">Template</p><p className="font-semibold">#{sub.form_template_id}</p></div><div><p className="text-[#737780]">Mapping basis</p><p className="font-semibold">{sub.mapping_basis.replaceAll("_"," ")}</p></div><div><p className="text-[#737780]">Completion</p><p className="font-semibold">{Number(sub.completion_pct).toFixed(0)}%</p></div><div><p className="text-[#737780]">Blockers</p><p className="font-semibold text-red-700">{data.approval_blockers.length}</p></div></div></div>
    {data.legacy_warning&&<div className="flex gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-900"><FileWarning className="shrink-0"/><div><h2 className="font-semibold">{data.legacy_warning.title}</h2><p className="mt-1 text-sm">{data.legacy_warning.message}</p><p className="mt-2 text-xs">Historical values are preserved. Newer form-version data is never substituted here.</p></div></div>}
    <div className="flex border-b">{[["data","Form Data"],["requirements","PRD & Validation"],["actions","Review & Actions"]].map(([key,label])=><button key={key} onClick={()=>setTab(key as typeof tab)} className={`border-b-2 px-5 py-3 text-sm font-semibold ${tab===key?"border-[#001836] text-[#001836]":"border-transparent text-[#737780]"}`}>{label}{key==="requirements"&&<span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800">{data.requirements.filter(r=>r.status!=="MATCHED").length+data.approval_blockers.length}</span>}</button>)}</div>
    {tab==="data"&&<div className="space-y-4">{data.template.sections.map(section=><SectionPanel key={section.id} section={section} data={data} canReview={canReview&&underReview} selected={selected} toggle={toggle} refresh={refresh}/>)}</div>}
    {tab==="requirements"&&<div className="grid gap-5 lg:grid-cols-2"><section className="rounded-2xl border bg-white p-5"><h2 className="font-semibold">Section 11 requirements</h2><div className="mt-4 space-y-3">{data.requirements.map(item=><div key={item.id} className="rounded-xl border p-4"><div className="flex justify-between gap-3"><p className="font-medium">{item.requirement_label}</p><span className={`h-fit rounded-full px-2 py-1 text-xs font-semibold ${badge[item.status]??"bg-gray-100"}`}>{item.status}</span></div><p className="mt-1 text-xs text-[#737780]">{item.requirement_type.replaceAll("_"," ")} · {item.severity}</p><p className="mt-2 text-sm">{item.evidence}</p></div>)}</div></section><div className="space-y-5"><section className="rounded-2xl border bg-white p-5"><div className="flex justify-between"><h2 className="font-semibold">Validation</h2><span className={`rounded-full px-2 py-1 text-xs font-semibold ${badge[data.validation?.status??""]??"bg-gray-100"}`}>{data.validation?.status??"Not run"}</span></div><div className="mt-4 space-y-2">{data.validation?.results.length?data.validation.results.map(x=><div key={x.id} className="rounded-xl bg-red-50 p-3 text-sm text-red-800"><p className="font-semibold">{x.code}</p><p>{x.message}</p></div>):<p className="text-sm text-green-700">No validation failures.</p>}</div></section><section className="rounded-2xl border bg-white p-5"><h2 className="font-semibold">Approval blockers</h2><div className="mt-3 space-y-2">{data.approval_blockers.length?data.approval_blockers.map((x,i)=><div key={`${x.code}-${i}`} className="flex gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-800"><AlertTriangle size={16} className="shrink-0"/><span>{x.label}</span></div>):<p className="text-sm text-green-700">No blocking issues.</p>}</div></section></div></div>}
    {tab==="actions"&&<div className="grid gap-5 lg:grid-cols-2"><section className="rounded-2xl border bg-white p-5"><h2 className="font-semibold">Regulatory decision</h2>{canReview&&canStart&&<button onClick={()=>start.mutate()} disabled={start.isPending} className="mt-4 rounded-xl bg-[#001836] px-4 py-2.5 text-sm font-semibold text-white"><Clock size={15} className="mr-2 inline"/>Start review</button>}{canReview&&underReview&&<><p className="mt-2 text-sm text-[#737780]">{selected.size} correction target(s) selected in Form Data.</p><div className="mt-4 grid grid-cols-2 gap-2">{[["approve","Approve",CheckCircle2],["reject","Reject",XCircle],["correction","Request correction",AlertTriangle],["note","Internal note",MessageSquare]].map(([key,label,Icon])=><button key={key as string} onClick={()=>setAction(key as typeof action)} className="flex items-center gap-2 rounded-xl border p-3 text-sm font-semibold"><Icon size={16}/>{label as string}</button>)}</div>{action&&<div className="mt-4 space-y-3"><textarea value={comment} onChange={e=>setComment(e.target.value)} className="min-h-28 w-full rounded-xl border p-3 text-sm" placeholder={action==="approve"?"Optional approval note":"Required reason or instruction"}/>{error&&<p className="text-sm text-red-700">{error}</p>}<button disabled={mutation.isPending} onClick={()=>mutation.mutate()} className="rounded-xl bg-[#001836] px-4 py-2.5 text-sm font-semibold text-white">Confirm {action.replaceAll("_"," ")}</button></div>}</>}{!canStart&&!underReview&&<p className="mt-3 text-sm text-[#737780]">No regulatory action is available in the current status.</p>}</section><section className="rounded-2xl border bg-white p-5"><h2 className="font-semibold">Review history</h2><div className="mt-4 space-y-3">{history.data?.length?history.data.map(item=><div key={item.id} className="border-b pb-3"><div className="flex justify-between gap-3"><p className="text-sm font-semibold">{item.action.replaceAll("_"," ")}</p><p className="text-xs text-[#737780]">{formatDateTime(item.created_at)}</p></div><p className="text-xs text-[#737780]">{item.created_by_name}{item.target_type?` · ${item.target_type} ${item.target_id}`:""}</p>{item.comment&&<p className="mt-1 text-sm">{item.comment}</p>}</div>):<p className="text-sm text-[#737780]">No review actions yet.</p>}</div></section></div>}
  </div>;
}

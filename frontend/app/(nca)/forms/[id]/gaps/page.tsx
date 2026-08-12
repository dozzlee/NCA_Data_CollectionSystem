"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RefreshCw, ShieldAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { FormGapAssessment, FormTemplate } from "@/lib/types";

const statusStyle: Record<string,string> = { MATCHED:"bg-green-100 text-green-800", MISSING:"bg-red-100 text-red-800", PARTIAL:"bg-amber-100 text-amber-800", NOT_APPLICABLE:"bg-gray-100 text-gray-700" };

export default function GapAnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [error, setError] = useState("");
  const { data: form } = useQuery<FormTemplate>({ queryKey:["form-template",id], queryFn:()=>api(`/form-templates/${id}/`) });
  const { data, isLoading } = useQuery<{ results?: FormGapAssessment[] }|FormGapAssessment[]>({ queryKey:["form-gaps",id], queryFn:()=>api(`/form-templates/${id}/gaps/`) });
  const gaps = useMemo(()=>Array.isArray(data)?data:data?.results??[],[data]);
  const filtered = gaps.filter(item=>(!status||item.status===status)&&(!severity||item.severity===severity));
  const counts = Object.fromEntries(["MATCHED","PARTIAL","MISSING","NOT_APPLICABLE"].map(key=>[key,gaps.filter(item=>item.status===key).length]));
  const recalc = useMutation({ mutationFn:()=>api.post(`/form-templates/${id}/gaps/recalculate/`,{}), onSuccess:()=>qc.invalidateQueries({queryKey:["form-gaps",id]}), onError:(e:Error)=>setError(e.message) });
  async function resolve(item:FormGapAssessment){const resolution=window.prompt("Add resolution evidence. Automated requirements remain open until the form structure actually matches.");if(!resolution?.trim())return;setError("");try{await api.post(`/form-gaps/${item.id}/resolve/`,{resolution_note:resolution.trim()});await qc.invalidateQueries({queryKey:["form-gaps",id]});}catch(e){setError(e instanceof ApiError?e.message:"Resolution failed.")}}

  return <div className="space-y-6"><a href={`/forms/${id}`} className="text-sm font-semibold text-[#0066cc]">← Back to form</a><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-mono text-xs text-[#0066cc]">{form?.form_code}</p><h1 className="mt-1 text-3xl font-semibold">Gap Analysis</h1><p className="mt-1 text-sm text-[#737780]">Version-specific comparison against the retained Section 11 requirements.</p></div><button disabled={recalc.isPending} onClick={()=>recalc.mutate()} className="flex items-center gap-2 rounded-xl bg-[#001836] px-4 py-2.5 text-sm font-semibold text-white"><RefreshCw size={15} className={recalc.isPending?"animate-spin":""}/> Recalculate</button></div>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{[["Matched","MATCHED"],["Partial","PARTIAL"],["Missing","MISSING"],["Not applicable","NOT_APPLICABLE"]].map(([label,key])=><div key={key} className="rounded-2xl border bg-white p-5"><p className="text-xs uppercase text-[#737780]">{label}</p><p className="mt-1 text-2xl font-semibold">{counts[key]??0}</p></div>)}</div>
    <div className="flex gap-3"><select value={status} onChange={e=>setStatus(e.target.value)} className="rounded-xl border px-3 py-2 text-sm"><option value="">All statuses</option><option>MATCHED</option><option>PARTIAL</option><option>MISSING</option><option>NOT_APPLICABLE</option></select><select value={severity} onChange={e=>setSeverity(e.target.value)} className="rounded-xl border px-3 py-2 text-sm"><option value="">All severities</option><option>BLOCKER</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></div>
    {error&&<p className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>}{isLoading&&<p className="rounded-2xl bg-white p-8 text-sm text-[#737780]">Loading assessment…</p>}
    <div className="space-y-3">{filtered.map(item=><div key={item.id} className="rounded-2xl border bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-start gap-3">{item.status==="MATCHED"?<CheckCircle2 className="mt-0.5 text-green-700" size={18}/>:<ShieldAlert className="mt-0.5 text-amber-700" size={18}/>}<div><p className="font-semibold">{item.requirement_label}</p><p className="mt-1 text-sm text-[#737780]">{item.evidence}</p><p className="mt-2 text-xs text-[#737780]">{item.requirement_type.replace("_"," ")} · {item.severity}</p>{item.resolution_note&&<p className="mt-2 rounded-lg bg-green-50 p-2 text-xs text-green-800">Resolution: {item.resolution_note}</p>}</div></div><div className="flex items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyle[item.status]}`}>{item.status.replace("_"," ")}</span>{["MISSING","PARTIAL"].includes(item.status)&&<button onClick={()=>resolve(item)} className="rounded-lg border px-3 py-1.5 text-xs font-semibold">Add evidence</button>}</div></div></div>)}</div>
  </div>;
}

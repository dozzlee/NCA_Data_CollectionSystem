"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { Skeleton } from "@/components/ui/Skeleton";
import type { FormTemplate, FormWorkbookImport } from "@/lib/types";

export default function WorkbookImportPreviewPage() {
  const { id } = useParams<{id:string}>();
  const router = useRouter();
  const { toast } = useToast();
  const [schemaText, setSchemaText] = useState("");
  const [resolvedWarnings, setResolvedWarnings] = useState<string[]>([]);
  const query = useQuery<FormWorkbookImport>({
    queryKey:["form-workbook-import",id],
    queryFn:async()=>{ const item=await api<FormWorkbookImport>(`/form-workbook-imports/${id}/`); setSchemaText(current=>current||JSON.stringify(item.detected_schema,null,2)); setResolvedWarnings(current=>current.length?current:((item.mapping_decisions.resolved_warning_codes as string[]|undefined)??[])); return item; },
  });
  const save = useMutation({
    mutationFn:()=>api<FormWorkbookImport>(`/form-workbook-imports/${id}/`,{method:"PATCH",body:JSON.stringify({detected_schema:JSON.parse(schemaText),mapping_decisions:{reviewed:true,resolved_warning_codes:resolvedWarnings}})}),
    onSuccess:()=>toast("Workbook mapping saved.","success"), onError:(error:Error)=>toast(error.message,"error"),
  });
  const confirm = useMutation({
    mutationFn:async()=>{ await save.mutateAsync(); return api<FormTemplate>(`/form-workbook-imports/${id}/confirm/`,{method:"POST"}); },
    onSuccess:form=>{toast("Draft form generated from the workbook.","success");router.push(`/forms/${form.id}`);},
    onError:(error:Error)=>toast(error.message,"error"),
  });
  if(query.isLoading)return <div className="space-y-4"><Skeleton className="h-8 w-72"/><Skeleton className="h-96"/></div>;
  const item=query.data;
  if(!item)return <p>Workbook import not found.</p>;
  const sections=item.detected_schema.sections??[];
  const hasUnresolvedBlockingWarning=item.warnings.some(w=>w.severity==="BLOCKING"&&!resolvedWarnings.includes(w.code));
  return <div className="max-w-5xl space-y-6">
    <Link href="/forms" className="text-sm text-[#0066cc]">← Form Templates</Link>
    <div><h1 className="text-2xl font-semibold">Workbook form preview</h1><p className="mt-1 text-sm text-[#43474f]">{item.form_code} · {item.name} · v{item.version}</p></div>
    <div className="grid gap-3 sm:grid-cols-4">
      {[['Scan',item.scan_status],['Parsing',item.parse_status],['Sheets',String(sections.length)],['Parser',item.parser_version]].map(([label,value])=><div key={label} className="rounded-xl border bg-white p-4"><p className="text-[11px] font-semibold uppercase text-[#737780]">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>)}
    </div>
    {item.warnings.length>0&&<div className="rounded-xl border border-amber-300 bg-amber-50 p-4"><h2 className="text-sm font-semibold">Mapping warnings</h2>{item.warnings.map(w=><div key={w.code} className="mt-2 flex items-start gap-2 text-xs"><input type="checkbox" checked={resolvedWarnings.includes(w.code)} onChange={event=>setResolvedWarnings(current=>event.target.checked?[...current,w.code]:current.filter(code=>code!==w.code))} aria-label={`Resolve ${w.code}`} className="mt-0.5"/><span><strong>{w.severity}:</strong> {w.message}</span></div>)}</div>}
    <div className="rounded-xl border bg-white p-5"><h2 className="text-sm font-semibold">Detected structure</h2><div className="mt-3 space-y-3">{sections.map(section=><div key={section.section_code} className="rounded-lg bg-[#f7f9fb] p-3"><p className="text-sm font-semibold">{section.title} <span className="font-mono text-xs text-[#737780]">{section.section_code}</span></p><p className="mt-1 text-xs text-[#43474f]">{section.fields.length} fields · {section.grids.length} tables</p></div>)}</div></div>
    <div className="rounded-xl border bg-white p-5"><label className="text-sm font-semibold">Editable schema mapping</label><p className="mt-1 text-xs text-[#737780]">Review labels, required flags, field types, grids and fixed rows. Cell values are intentionally absent.</p><textarea aria-label="Workbook schema JSON" value={schemaText} onChange={e=>setSchemaText(e.target.value)} rows={24} className="mt-3 w-full rounded-lg border p-3 font-mono text-xs"/><div className="mt-3 flex justify-end gap-2"><button onClick={()=>save.mutate()} disabled={save.isPending} className="rounded-lg border px-4 py-2 text-sm">Save mapping</button><button onClick={()=>confirm.mutate()} disabled={confirm.isPending||item.scan_status!=="CLEAN"||item.parse_status!=="READY"||hasUnresolvedBlockingWarning} className="rounded-lg bg-[#001836] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Confirm & create draft</button></div></div>
  </div>;
}

"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, FileSpreadsheet, RefreshCw, Upload } from "lucide-react";
import { api } from "@/lib/api";
import type { FormSection, SubmissionExcelImport, SubmissionExcelImportMatch } from "@/lib/types";

interface Props { submissionId:number; sections:FormSection[]; disabled?:boolean }
type Target = { key:string; label:string; target_type:"FIELD"|"GRID_CELL"; field?:number; grid?:number; grid_row_id?:string; grid_column?:number; repeatable?:boolean };
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export function ExcelBackupPanel({ submissionId, sections, disabled=false }: Props) {
  const qc=useQueryClient();
  const [selectedId,setSelectedId]=useState<number|null>(null);
  const [uploadError,setUploadError]=useState("");
  const [allowUnresolved,setAllowUnresolved]=useState(false);
  const [overwriteIds,setOverwriteIds]=useState<number[]>([]);
  const [matchPage,setMatchPage]=useState(1);
  const [matchStatus,setMatchStatus]=useState("");
  const [confirmKey]=useState(()=>crypto.randomUUID());
  const imports=useQuery<SubmissionExcelImport[]>({queryKey:["excel-imports",submissionId],queryFn:()=>api(`/submissions/${submissionId}/excel-imports/`)});
  const activeId=selectedId??imports.data?.[0]?.id??null;
  const detail=useQuery<SubmissionExcelImport>({queryKey:["excel-import",activeId,matchPage,matchStatus],queryFn:()=>api(`/excel-imports/${activeId}/?page=${matchPage}&page_size=50${matchStatus?`&status=${matchStatus}`:""}`),enabled:Boolean(activeId),refetchInterval:q=>["SCANNING","PARSING"].includes(q.state.data?.status??"")?1500:false});
  const targets=useMemo<Target[]>(()=>sections.flatMap(section=>[
    ...section.fields.filter(field=>!["formula","attachment"].includes(field.field_type)).map(field=>({key:`FIELD:${field.id}`,label:`${section.title} · ${field.label}`,target_type:"FIELD" as const,field:field.id})),
    ...section.grids.flatMap(grid=>grid.row_mode==="REPEATABLE"
      ?grid.columns.map(column=>({key:`GRID_CELL:${grid.id}:REPEATABLE:${column.id}`,label:`${section.title} · ${grid.title} · Imported row · ${column.label}`,target_type:"GRID_CELL" as const,grid:grid.id,grid_row_id:"REPEATABLE",grid_column:column.id,repeatable:true}))
      :(grid.fixed_rows??[]).flatMap(row=>grid.columns.map(column=>({key:`GRID_CELL:${grid.id}:${row.id}:${column.id}`,label:`${section.title} · ${grid.title} · ${row.row_label} · ${column.label}`,target_type:"GRID_CELL" as const,grid:grid.id,grid_row_id:String(row.id),grid_column:column.id})))),
  ]),[sections]);
  const upload=useMutation({mutationFn:async(file:File)=>{
    if(!file.name.toLowerCase().endsWith(".xlsx"))throw new Error("Only .xlsx workbooks are accepted.");
    if(file.size>MAX_UPLOAD_BYTES)throw new Error("The workbook is larger than the 20 MB upload limit.");
    const form=new FormData();form.append("file",file);
    try{return await api.upload<SubmissionExcelImport>(`/submissions/${submissionId}/excel-imports/`,form);}
    catch(error){
      if(error instanceof TypeError&&error.message==="Failed to fetch")throw new Error("The workbook could not reach the server. Check that the backend is running on port 8001, then retry.");
      throw error;
    }
  },onSuccess:item=>{setSelectedId(item.id);setMatchPage(1);setMatchStatus("");setOverwriteIds([]);setUploadError("");qc.invalidateQueries({queryKey:["excel-imports",submissionId]});},onError:(error:Error)=>setUploadError(error.message)});
  const mapMatch=useMutation({mutationFn:({match,target}:{match:SubmissionExcelImportMatch;target:Target|null})=>{const resolved=target?.repeatable?{...target,grid_row_id:`excel-${match.source_sheet.toLowerCase().replace(/[^a-z0-9]+/g,"-").slice(0,30)}-${match.source_row}`} : target;return api.patch(`/excel-imports/${activeId}/matches/`,{matches:[resolved?{id:match.id,action:"MAP",...resolved}:{id:match.id,action:"SKIP"}]});},onSuccess:()=>qc.invalidateQueries({queryKey:["excel-import",activeId]})});
  const confirm=useMutation({mutationFn:()=>api.post<SubmissionExcelImport>(`/excel-imports/${activeId}/confirm/`,{confirmation_key:confirmKey,overwrite_match_ids:overwriteIds,allow_unresolved:allowUnresolved}),onSuccess:()=>{qc.invalidateQueries({queryKey:["excel-import",activeId]});qc.invalidateQueries({queryKey:["section-values"]});qc.invalidateQueries({queryKey:["submission",submissionId]});qc.invalidateQueries({queryKey:["submission-completion",submissionId]});}});
  const reparse=useMutation({mutationFn:()=>api.post(`/excel-imports/${activeId}/reparse/`,{}),onSuccess:()=>qc.invalidateQueries({queryKey:["excel-import",activeId]})});
  const item=detail.data;
  const unresolvedCount=item?Object.entries(item.summary.counts??{}).filter(([status])=>!["MATCHED","SKIPPED"].includes(status)).reduce((total,[,count])=>total+Number(count??0),0):0;
  const overwrite=item?.matches.filter(match=>match.status==="MATCHED"&&match.will_overwrite)??[];
  const selectedTargetValue=(match:SubmissionExcelImportMatch)=>{
    if(match.status==="SKIPPED")return "SKIP";
    if(match.target_type==="FIELD")return `FIELD:${match.field}`;
    if(match.target_type==="GRID_CELL"){
      const repeatable=targets.find(target=>target.repeatable&&target.grid===match.grid&&target.grid_column===match.grid_column);
      return repeatable?.key??`GRID_CELL:${match.grid}:${match.grid_row_id}:${match.grid_column}`;
    }
    return "";
  };

  return <section className="rounded-xl border border-[#cdd9e5] bg-[#f7fbff] p-5">
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start"><div><h3 className="flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet size={17}/> Import Excel data</h3><p className="mt-1 text-xs text-[#5e6269]">Upload a private .xlsx workbook (maximum 20 MB), review the suggested indicator matches, then populate this editable form.</p></div>{!disabled&&<label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-[#0066cc] px-4 py-2 text-xs font-semibold text-white"><Upload size={14}/>{upload.isPending?"Uploading…":"Upload .xlsx"}<input className="hidden" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={upload.isPending} onChange={event=>{const file=event.target.files?.[0];event.target.value="";if(file)upload.mutate(file);}}/></label>}</div>
    {uploadError&&<p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">{uploadError}</p>}
    {(imports.data?.length??0)>0&&<div className="mt-4 flex flex-wrap gap-2">{imports.data!.map(row=><button key={row.id} onClick={()=>{setSelectedId(row.id);setMatchPage(1);setMatchStatus("");setOverwriteIds([]);}} className={`rounded-lg border px-3 py-1.5 text-[11px] ${activeId===row.id?"border-[#0066cc] bg-white text-[#004999]":"border-[#dce3e9] text-[#5e6269]"}`}>{row.file_name} · {row.status}</button>)}</div>}
    {detail.isLoading&&<p className="mt-4 flex items-center gap-2 text-xs text-[#004999]"><RefreshCw size={13} className="animate-spin"/>Loading import preview…</p>}
    {item&&["SCANNING","PARSING"].includes(item.status)&&<p className="mt-4 flex items-center gap-2 rounded-lg bg-blue-50 p-3 text-xs text-[#004999]"><RefreshCw size={13} className="animate-spin"/>The workbook is being scanned and matched. You can keep this page open; the preview will update automatically.</p>}
    {item&&<div className="mt-4 space-y-4">
      <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">{[["Detected",item.summary.detected??0],["Matched",item.summary.counts?.MATCHED??0],["Unmatched",item.summary.counts?.UNMATCHED??0],["Ambiguous",item.summary.counts?.AMBIGUOUS??0],["Invalid",item.summary.counts?.INVALID??0],["Required missing",item.summary.missing_required??0]].map(([label,value])=><div key={label} className="rounded-lg border bg-white p-3"><p className="text-[10px] uppercase text-[#737780]">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>)}</div>
      {(item.summary.warnings?.length??0)>0&&<div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900"><p className="font-semibold">Workbook extraction warnings</p>{item.summary.warnings!.map((warning,index)=><p key={`${warning.sheet}-${warning.row??0}-${index}`} className="mt-1">{warning.sheet}{warning.row?` · row ${warning.row}`:""}: {warning.message}</p>)}</div>}
      {item.errors.length>0&&<div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{item.errors.map(error=><p key={error.code}>{error.message}</p>)}</div>}
      {item.status==="READY"&&<><div className="flex flex-wrap items-center justify-between gap-2"><label className="text-xs text-[#5e6269]">Show <select value={matchStatus} onChange={event=>{setMatchStatus(event.target.value);setMatchPage(1);}} className="ml-2 rounded border bg-white px-2 py-1.5"><option value="">All matches</option>{["MATCHED","UNMATCHED","AMBIGUOUS","DUPLICATE","INVALID","SKIPPED"].map(status=><option key={status} value={status}>{status}</option>)}</select></label><span className="text-xs text-[#737780]">{item.matches_meta.count.toLocaleString()} result{item.matches_meta.count===1?"":"s"}</span></div><div className="max-h-[430px] overflow-auto rounded-lg border bg-white"><table className="w-full min-w-[900px] text-left text-xs"><thead className="sticky top-0 bg-[#eef3f8] text-[10px] uppercase text-[#5e6269]"><tr><th className="p-3">Workbook indicator</th><th className="p-3">Value</th><th className="p-3">Match</th><th className="p-3">Current value</th><th className="p-3">Status</th></tr></thead><tbody className="divide-y">{item.matches.map(match=><tr key={match.id}><td className="p-3"><p className="font-medium">{match.indicator_name}</p><p className="mt-1 text-[10px] text-[#737780]">{match.source_locator}{match.indicator_code?` · ${match.indicator_code}`:""}</p></td><td className="p-3 break-all">{String(match.raw_value??"—")}</td><td className="p-3"><select value={selectedTargetValue(match)} onChange={event=>{if(event.target.value==="SKIP")mapMatch.mutate({match,target:null});else{const target=targets.find(row=>row.key===event.target.value)??null;if(target)mapMatch.mutate({match,target});}}} className="w-full rounded border px-2 py-1.5"><option value="">Review match</option>{targets.map(target=><option key={target.key} value={target.key}>{target.label}</option>)}<option value="SKIP">Skip this indicator</option></select>{match.target_label&&<p className="mt-1 text-[10px] text-[#737780]">Suggested: {match.target_label} · {(Number(match.score)*100).toFixed(0)}%</p>}<p className="mt-1 text-[10px] text-[#737780]">Match basis: {String(match.evidence.match_reason??"No confident match").replaceAll("_"," ")}</p></td><td className="p-3">{match.current_value||"—"}{match.will_overwrite&&<label className="mt-1 flex gap-1 text-[10px] text-amber-800"><input type="checkbox" checked={overwriteIds.includes(match.id)} onChange={event=>setOverwriteIds(ids=>event.target.checked?[...ids,match.id]:ids.filter(id=>id!==match.id))}/>Confirm replacement</label>}</td><td className="p-3"><span className={`rounded-full px-2 py-1 text-[9px] font-semibold ${match.status==="MATCHED"?"bg-green-100 text-green-800":match.status==="SKIPPED"?"bg-gray-100 text-gray-700":"bg-amber-100 text-amber-800"}`}>{match.status}</span></td></tr>)}</tbody></table></div>{item.matches_meta.pages>1&&<div className="flex items-center justify-end gap-2 text-xs"><button onClick={()=>setMatchPage(page=>Math.max(1,page-1))} disabled={item.matches_meta.page<=1} className="rounded border bg-white px-3 py-1.5 disabled:opacity-40">Previous</button><span>Page {item.matches_meta.page} of {item.matches_meta.pages}</span><button onClick={()=>setMatchPage(page=>Math.min(item.matches_meta.pages,page+1))} disabled={item.matches_meta.page>=item.matches_meta.pages} className="rounded border bg-white px-3 py-1.5 disabled:opacity-40">Next</button></div>}</>}
      {item.status==="READY"&&!disabled&&<div className="flex flex-col justify-between gap-3 rounded-lg border bg-white p-4 sm:flex-row sm:items-center"><label className="flex items-start gap-2 text-xs"><input type="checkbox" checked={allowUnresolved} onChange={event=>setAllowUnresolved(event.target.checked)} className="mt-0.5"/><span>Import valid matches and leave {unresolvedCount} unresolved indicator{unresolvedCount===1?"":"s"} blank.</span></label><div className="flex gap-2"><button onClick={()=>reparse.mutate()} className="rounded-lg border px-3 py-2 text-xs">Reparse</button><button onClick={()=>confirm.mutate()} disabled={confirm.isPending||(!allowUnresolved&&unresolvedCount>0)||overwrite.some(row=>!overwriteIds.includes(row.id))} className="rounded-lg bg-[#1f7a4d] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40">{confirm.isPending?"Importing…":"Confirm and populate form"}</button></div></div>}
      {confirm.error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{confirm.error.message}</p>}
      {item.status==="IMPORTED"&&<div className={`rounded-lg p-3 text-xs ${item.imported_manifest.reconciled?"bg-green-50 text-green-800":"bg-amber-50 text-amber-900"}`}><p className="flex items-center gap-2"><Check size={14}/>Imported {item.imported_manifest.changed_targets??0} changed values. You can review and edit them before submission.</p>{!item.imported_manifest.reconciled&&<p className="mt-2">{item.imported_manifest.unresolved_populated?.length??0} populated workbook value(s) remained unresolved and were not imported.</p>}</div>}
      {item.status==="FAILED"&&<div className="flex items-start justify-between gap-3 rounded-lg bg-red-50 p-3 text-xs text-red-700"><p className="flex items-start gap-2"><AlertCircle size={14} className="mt-0.5 shrink-0"/><span>{item.errors[0]?.message??"The workbook could not be processed."}</span></p>{!disabled&&<button onClick={()=>reparse.mutate()} disabled={reparse.isPending} className="shrink-0 rounded border border-red-200 bg-white px-2 py-1 font-semibold">{reparse.isPending?"Retrying…":"Retry"}</button>}</div>}
    </div>}
  </section>;
}

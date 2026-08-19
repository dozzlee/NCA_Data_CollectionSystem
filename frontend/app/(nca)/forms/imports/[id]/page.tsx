"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { Skeleton } from "@/components/ui/Skeleton";
import type { FormTemplate, FormWorkbookImport } from "@/lib/types";

type ImportedSection = NonNullable<FormWorkbookImport["detected_schema"]["sections"]>[number];
type ImportedField = ImportedSection["fields"][number];
type ColumnMapping = Omit<ImportedSection["column_mapping"], "candidates" | "detected">;

function FieldPreview({ field }: { field: ImportedField }) {
  const inputClass = "mt-2 w-full rounded-lg border border-[#d9dde3] bg-[#f7f9fb] px-3 py-2 text-sm text-[#737780]";
  return (
    <div className="rounded-xl border border-[#eceef0] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <label className="text-sm font-semibold text-[#191c1e]">{field.label}</label>
        {field.is_required && <span className="rounded-full bg-[#e8f1fb] px-2 py-0.5 text-[10px] font-semibold text-[#004999]">Requested</span>}
      </div>
      {(field.help_text || field.unit) && <p className="mt-1 text-xs text-[#737780]">{field.help_text || `Unit: ${field.unit}`}</p>}
      {field.field_type === "textarea" ? (
        <textarea disabled rows={3} placeholder="Provider response" className={inputClass} />
      ) : field.field_type === "select" ? (
        <select disabled className={inputClass}><option>Select an option</option>{field.options.map(option => <option key={option}>{option}</option>)}</select>
      ) : field.field_type === "boolean" ? (
        <label className="mt-3 flex items-center gap-2 text-sm text-[#737780]"><input type="checkbox" disabled /> Yes / No</label>
      ) : field.field_type === "formula" ? (
        <div className={`${inputClass} min-h-10`}>Calculated after data entry</div>
      ) : (
        <input disabled type={field.field_type === "date" ? "date" : field.field_type === "number" || field.field_type === "percentage" ? "number" : "text"} placeholder="Provider response" className={inputClass} />
      )}
    </div>
  );
}

function SectionFieldsPreview({ section }: { section: ImportedSection }) {
  const items = [
    ...(section.headings??[]).map(heading => ({ kind:"heading" as const, order:heading.source_order, heading })),
    ...section.fields.map(field => ({ kind:"field" as const, order:field.source_order, field })),
  ].sort((left,right)=>left.order-right.order);
  return <div className="space-y-4">{items.map(item => item.kind === "heading" ? (
    <div key={`heading-${item.heading.heading_code}`} className={item.heading.level===1?"border-b-2 border-[#001836] pb-2 pt-2":item.heading.level===2?"border-l-4 border-[#0066cc] bg-[#e8f1fb] px-4 py-2":"border-l-2 border-[#8aa9c7] pl-3"}>
      <h3 className={item.heading.level===1?"text-base font-semibold text-[#001836]":"text-sm font-semibold text-[#23364d]"}>{item.heading.title}</h3>
    </div>
  ) : <FieldPreview key={`field-${item.field.field_code}`} field={item.field}/>)}</div>;
}

export default function WorkbookImportPreviewPage() {
  const { id } = useParams<{id:string}>();
  const router = useRouter();
  const { toast } = useToast();
  const [schemaText, setSchemaText] = useState("");
  const [resolvedWarnings, setResolvedWarnings] = useState<string[]>([]);
  const [activeSectionCode, setActiveSectionCode] = useState("");
  const [columnMappings, setColumnMappings] = useState<Record<string,ColumnMapping>>({});
  const [schemaDirty, setSchemaDirty] = useState(false);
  const [loadedSchemaVersion, setLoadedSchemaVersion] = useState("");
  const [newerSchemaAvailable, setNewerSchemaAvailable] = useState(false);

  const query = useQuery<FormWorkbookImport>({
    queryKey:["form-workbook-import",id],
    queryFn:()=>api<FormWorkbookImport>(`/form-workbook-imports/${id}/`),
    refetchInterval: currentQuery => currentQuery.state.data?.parse_status === "PENDING" ? 1500 : false,
  });

  useEffect(() => {
    const item = query.data;
    if (!item) return;
    const serverVersion = `${item.updated_at}:${item.parser_version}`;
    if (!loadedSchemaVersion) {
      setSchemaText(JSON.stringify(item.detected_schema ?? {}, null, 2));
      setLoadedSchemaVersion(serverVersion);
      setSchemaDirty(false);
    } else if (serverVersion !== loadedSchemaVersion) {
      if (schemaDirty) setNewerSchemaAvailable(true);
      else {
        setSchemaText(JSON.stringify(item.detected_schema ?? {}, null, 2));
        setLoadedSchemaVersion(serverVersion);
        setNewerSchemaAvailable(false);
      }
    }
    setResolvedWarnings(current => current.length ? current : ((item.mapping_decisions.resolved_warning_codes as string[]|undefined) ?? []));
    setColumnMappings(current => Object.keys(current).length ? current : ((item.mapping_decisions.column_mappings as Record<string,ColumnMapping>|undefined) ?? {}));
  }, [query.data, loadedSchemaVersion, schemaDirty]);

  const editorSchema = useMemo(() => {
    try {
      const parsed = JSON.parse(schemaText || "{}");
      return { schema: parsed as FormWorkbookImport["detected_schema"], error: "" };
    } catch {
      return { schema: query.data?.detected_schema ?? {}, error: "The worksheet mapping contains invalid JSON." };
    }
  }, [schemaText, query.data]);
  const sections = useMemo(() => editorSchema.schema.sections ?? [], [editorSchema]);

  useEffect(() => {
    if (!sections.length) {
      setActiveSectionCode("");
      return;
    }
    if (!sections.some(section => section.section_code === activeSectionCode)) {
      setActiveSectionCode(sections[0].section_code);
    }
  }, [sections, activeSectionCode]);

  const save = useMutation({
    mutationFn:()=>api<FormWorkbookImport>(`/form-workbook-imports/${id}/`,{method:"PATCH",body:JSON.stringify({detected_schema:JSON.parse(schemaText),mapping_decisions:{...(query.data?.mapping_decisions??{}),reviewed:true,resolved_warning_codes:resolvedWarnings,column_mappings:columnMappings}})}),
    onSuccess:(updated)=>{
      setSchemaText(JSON.stringify(updated.detected_schema??{},null,2));
      setLoadedSchemaVersion(`${updated.updated_at}:${updated.parser_version}`);
      setSchemaDirty(false);
      setNewerSchemaAvailable(false);
      toast("Workbook mapping saved.","success");
      query.refetch();
    },
    onError:(error:Error)=>toast(error.message,"error"),
  });
  const confirm = useMutation({
    mutationFn:async()=>{ await save.mutateAsync(); return api<FormTemplate>(`/form-workbook-imports/${id}/confirm/`,{method:"POST"}); },
    onSuccess:form=>{toast("Draft form generated from the workbook.","success");router.push(`/forms/${form.id}`);},
    onError:(error:Error)=>toast(error.message,"error"),
  });
  const reparse = useMutation({
    mutationFn:()=>api<FormWorkbookImport>(`/form-workbook-imports/${id}/reparse/`,{method:"POST",body:JSON.stringify({column_mappings:columnMappings})}),
    onSuccess:updated=>{
      setSchemaText(JSON.stringify(updated.detected_schema??{},null,2));
      setLoadedSchemaVersion(`${updated.updated_at}:${updated.parser_version}`);
      setSchemaDirty(false);
      setNewerSchemaAvailable(false);
      const warningCodes=new Set(updated.warnings.map(warning=>warning.code));
      setResolvedWarnings(current=>current.filter(code=>warningCodes.has(code)));
      toast(updated.parse_status==="PENDING"?"Column mapping saved. The workbook is being analyzed again.":"Column mapping applied and preview refreshed.","success");
      query.refetch();
    },
    onError:(error:Error)=>toast(error.message,"error"),
  });

  if(query.isLoading)return <div className="space-y-4"><Skeleton className="h-8 w-72"/><Skeleton className="h-96"/></div>;
  if(query.isError)return <div className="rounded-xl border border-red-300 bg-red-50 p-5"><h1 className="font-semibold text-red-900">The workbook preview could not be loaded</h1><p className="mt-2 text-sm text-red-800">{query.error.message}</p><Link href="/forms" className="mt-4 inline-flex text-sm font-semibold text-[#0066cc]">Return to Form Templates</Link></div>;
  const item=query.data;
  if(!item)return <p>Workbook import not found.</p>;

  const hasUnresolvedBlockingWarning=item.warnings.some(w=>
    w.severity==="BLOCKING" &&
    (w.code.startsWith("MISSING_DEFINITION_COLUMNS_") || !resolvedWarnings.includes(w.code))
  );
  const isReady=item.scan_status==="CLEAN"&&item.parse_status==="READY";
  const isProcessing=item.scan_status==="PENDING"||item.parse_status==="PENDING";
  const activeSection=sections.find(section=>section.section_code===activeSectionCode)??sections[0];
  const activeMapping=activeSection?.column_mapping??{detected:true,header_row:null,indicator_column:null,definition_column:null,data_type_column:null,unit_column:null,required_column:null,options_column:null,candidates:[]};
  const statusProblem=item.scan_status==="INFECTED"||item.scan_status==="ERROR"||item.parse_status==="FAILED";
  const statusMessage=item.scan_details||(
    item.scan_status==="INFECTED" ? "The workbook failed malware scanning and cannot be previewed." :
    item.scan_status==="ERROR" ? "The malware scanner could not inspect this workbook." :
    item.parse_status==="FAILED" ? "The workbook structure could not be read." : ""
  );

  return <div className="max-w-6xl space-y-6">
    <Link href="/forms" className="text-sm text-[#0066cc]">← Form Templates</Link>
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-2xl font-semibold">Workbook form preview</h1><p className="mt-1 text-sm text-[#43474f]">{item.form_code} · {item.name} · v{item.version}</p><p className="mt-1 text-xs text-[#737780]">{item.file_name} · {(item.file_size/1024/1024).toFixed(1)} MB</p></div>
      {item.resulting_template_id && <Link href={`/forms/${item.resulting_template_id}`} className="rounded-lg bg-[#001836] px-4 py-2 text-sm font-semibold text-white">Open generated form</Link>}
    </div>
    <div className="grid gap-3 sm:grid-cols-4">
      {[['Scan',item.scan_status],['Parsing',item.parse_status],['Visible tabs',String(sections.length)],['Parser',item.parser_version]].map(([label,value])=><div key={label} className="rounded-xl border bg-white p-4"><p className="text-[11px] font-semibold uppercase text-[#737780]">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>)}
    </div>

    {isProcessing&&<div role="status" className="rounded-xl border border-blue-300 bg-blue-50 p-4"><h2 className="text-sm font-semibold text-blue-900">Analyzing workbook structure…</h2><p className="mt-2 text-sm text-blue-800">The file is safely stored. This page refreshes automatically while the worksheet tabs are scanned, so you can keep it open without uploading again.</p></div>}
    {statusProblem&&<div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4"><h2 className="text-sm font-semibold text-red-900">This workbook needs attention</h2><p className="mt-2 whitespace-pre-wrap text-sm text-red-800">{statusMessage}</p><p className="mt-2 text-xs text-red-700">Return to Form Templates and upload a readable, macro-free .xlsx workbook. No draft form was created.</p></div>}
    {item.warnings.length>0&&<div className="rounded-xl border border-amber-300 bg-amber-50 p-4"><h2 className="text-sm font-semibold">Mapping warnings</h2>{item.warnings.map(w=>{const requiresMapping=w.code.startsWith("MISSING_DEFINITION_COLUMNS_");return <div key={w.code} className="mt-2 flex items-start gap-2 text-xs"><input type="checkbox" checked={resolvedWarnings.includes(w.code)} disabled={!isReady||requiresMapping} onChange={event=>setResolvedWarnings(current=>event.target.checked?[...current,w.code]:current.filter(code=>code!==w.code))} aria-label={`Resolve ${w.code}`} className="mt-0.5"/><span><strong>{w.severity}:</strong> {w.message}{requiresMapping&&<span className="mt-1 block font-semibold">Choose Indicator and Definition columns in that worksheet below; this warning cannot be dismissed.</span>}</span></div>})}</div>}
    {newerSchemaAvailable&&<div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-300 bg-blue-50 p-4 text-sm text-blue-900"><span>A newer workbook analysis is available. Your unsaved advanced mapping has not been overwritten.</span><button type="button" onClick={()=>{setSchemaText(JSON.stringify(item.detected_schema??{},null,2));setLoadedSchemaVersion(`${item.updated_at}:${item.parser_version}`);setSchemaDirty(false);setNewerSchemaAvailable(false);}} className="rounded-lg bg-[#001836] px-4 py-2 text-xs font-semibold text-white">Load latest analysis</button></div>}

    {sections.length>0&&<div className="rounded-xl border bg-white p-5"><h2 className="text-sm font-semibold">Worksheet sections</h2><p className="mt-1 text-xs text-[#737780]">Each visible workbook tab becomes one isolated form section in the same order. Hidden worksheet rows are excluded.</p><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{sections.map(section=>{const gridInputs=section.counts?.grid_input_count??section.grids.reduce((total,grid)=>total+(grid.row_mode==="FIXED"?grid.fixed_rows.length*grid.columns.length:0),0);return <button type="button" onClick={()=>setActiveSectionCode(section.section_code)} key={section.section_code} className={`rounded-lg border p-3 text-left ${activeSectionCode===section.section_code?'border-[#0066cc] bg-[#e8f1fb]':'border-[#eceef0] bg-[#f7f9fb]'}`}><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-[#43474f]">Tab {section.worksheet_order}</span><p className="text-sm font-semibold">{section.title}</p>{section.fields.length===0&&section.grids.length===0&&<span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">Empty</span>}</div><p className="mt-1 text-xs text-[#43474f]">{section.fields.length} scalar fields · {section.grids.length} tables{gridInputs?` · ${gridInputs} table inputs`:""}</p>{section.row_visibility&&section.row_visibility.excluded_hidden_row_count>0&&<p className="mt-1 text-[10px] text-[#737780]">{section.row_visibility.excluded_hidden_row_count} hidden source rows excluded</p>}</button>})}</div></div>}

    {activeSection&&<section className="overflow-hidden rounded-2xl border border-[#d9dde3] bg-[#f7f9fb]">
      <div className="border-b border-[#d9dde3] bg-[#001836] px-6 py-5 text-white"><p className="text-xs font-semibold uppercase tracking-wide text-blue-200">Provider form preview · Tab {activeSection.worksheet_order}</p><h2 className="mt-1 text-xl font-semibold">{activeSection.title}</h2>{activeSection.instructions&&<p className="mt-1 text-sm text-blue-100">{activeSection.instructions}</p>}</div>
      <div className="space-y-6 p-5">
        {!activeMapping.detected&&<div className="rounded-xl border border-amber-300 bg-amber-50 p-4"><h3 className="text-sm font-semibold text-amber-950">Map this worksheet&apos;s metadata columns</h3><p className="mt-1 text-xs text-amber-900">Enter Excel column numbers. Indicator and Definition are required; the remaining columns are optional.</p><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{([['header_row','Header row'],['indicator_column','Indicator column'],['definition_column','Definition column'],['data_type_column','Data Type column'],['unit_column','Unit column'],['required_column','Required column'],['options_column','Options column']] as const).map(([key,label])=><label key={key} className="text-xs font-medium text-amber-950">{label}<input type="number" min={1} value={columnMappings[activeSection.source.sheet]?.[key]??activeMapping[key]??''} onChange={event=>setColumnMappings(current=>({...current,[activeSection.source.sheet]:{...(current[activeSection.source.sheet]??{}),[key]:event.target.value?Number(event.target.value):null}}))} className="mt-1 w-full rounded-lg border border-amber-300 bg-white px-3 py-2"/></label>)}</div>{activeMapping.candidates.length>0&&<div className="mt-3 text-xs text-amber-900"><strong>Detected labels:</strong> {activeMapping.candidates.flatMap(candidate=>candidate.columns.map(column=>`row ${candidate.row}, column ${column.column}: ${column.label}`)).slice(0,12).join(' · ')}</div>}<button type="button" onClick={()=>reparse.mutate()} disabled={reparse.isPending||!columnMappings[activeSection.source.sheet]?.indicator_column||!columnMappings[activeSection.source.sheet]?.definition_column} className="mt-3 rounded-lg bg-[#001836] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">{reparse.isPending?"Re-analyzing…":"Apply columns and re-analyze"}</button></div>}
        {(activeSection.fields.length>0||(activeSection.headings??[]).length>0)&&<SectionFieldsPreview section={activeSection}/>}
        {activeSection.grids.map(grid=><div key={grid.grid_code} className="overflow-hidden rounded-xl border border-[#d9dde3] bg-white"><div className="border-b bg-[#f2f4f6] px-4 py-3"><h3 className="text-sm font-semibold">{grid.title}</h3>{grid.instructions&&<p className="mt-1 text-xs text-[#737780]">{grid.instructions}</p>}</div><div className="overflow-x-auto"><table className="min-w-full text-left text-xs"><thead className="bg-[#f7f9fb]"><tr>{grid.columns.map(column=><th key={column.column_code} className="border-b px-3 py-2 font-semibold">{column.label}{column.unit&&<span className="ml-1 font-normal text-[#737780]">({column.unit})</span>}</th>)}</tr></thead><tbody>{(grid.fixed_rows.length?grid.fixed_rows.slice(0,5):["Provider row"]).map((row,index)=><tr key={`${row}-${index}`} className="border-b last:border-b-0">{grid.columns.map((column,columnIndex)=><td key={column.column_code} className="px-3 py-2 text-[#737780]">{columnIndex===0&&grid.fixed_rows.length?row:"—"}</td>)}</tr>)}</tbody></table></div>{grid.fixed_rows.length>5&&<p className="px-4 py-2 text-xs text-[#737780]">Plus {grid.fixed_rows.length-5} more fixed rows</p>}</div>)}
        {activeSection.fields.length===0&&activeSection.grids.length===0&&<div className="rounded-xl border border-dashed p-8 text-center text-sm text-[#737780]">This worksheet is empty. Keep it as an empty section or remove it from the mapping before confirming.</div>}
      </div>
    </section>}

    {isReady&&<details className="rounded-xl border bg-white p-5"><summary className="cursor-pointer text-sm font-semibold">Advanced worksheet mapping</summary><p className="mt-2 text-xs text-[#737780]">Edit section titles, labels, requested flags, field types, grids and fixed rows. Workbook values are intentionally excluded from provider answers.</p><textarea aria-label="Workbook schema JSON" value={schemaText} onChange={e=>{setSchemaText(e.target.value);setSchemaDirty(true);}} rows={24} className="mt-3 w-full rounded-lg border p-3 font-mono text-xs"/>{editorSchema.error&&<p className="mt-2 text-xs font-semibold text-red-700">{editorSchema.error}</p>}<div className="mt-3 flex justify-end gap-2"><button onClick={()=>save.mutate()} disabled={save.isPending||Boolean(editorSchema.error)} className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">Save mapping</button><button onClick={()=>confirm.mutate()} disabled={confirm.isPending||Boolean(editorSchema.error)||hasUnresolvedBlockingWarning} className="rounded-lg bg-[#001836] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{confirm.isPending?"Creating draft…":"Confirm & create draft"}</button></div></details>}
  </div>;
}

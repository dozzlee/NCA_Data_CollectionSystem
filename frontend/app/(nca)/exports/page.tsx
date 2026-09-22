"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Database, Download, FileSpreadsheet, Search } from "lucide-react";
import { api, downloadAuthenticated } from "@/lib/api";

type Summary = { forms:number; forms_sent:number; submitted:number; approved:number; providers:number };
type Period = { id:number; name:string; frequency:string; status:string };
type FormRow = { id:number; code:string; name:string; version:string; frequency:string; status:string; approval_status:string; sections:number; indicators:number; tables:number };
type SubmissionRow = { id:number; provider:string; form_code:string; form_name:string; period:string; workflow_status:string; sent_at:string; due_at:string; submission_id:number|null; submission_reference:string; completion_pct:string };
type Catalogue = { summary:Summary; periods:Period[]; forms:FormRow[]; submissions:SubmissionRow[]; approved_data_only:boolean };
type Tab = "data" | "forms";

export default function ExportsPage() {
  const [tab,setTab]=useState<Tab>("data");
  const [search,setSearch]=useState("");
  const [period,setPeriod]=useState("");
  const [selectedForms,setSelectedForms]=useState<number[]>([]);
  const [selectedSubmissions,setSelectedSubmissions]=useState<number[]>([]);
  const [downloading,setDownloading]=useState(false);
  const [message,setMessage]=useState("");
  const query=useQuery<Catalogue>({
    queryKey:["export-catalogue",period,search],
    queryFn:()=>api(`/exports/catalogue/?${new URLSearchParams({...(period?{period}:{}),...(search?{search}: {})})}`),
  });
  const periods=query.data?.periods??[];
  const forms=query.data?.forms??[];
  const submissions=query.data?.submissions??[];
  const summary=query.data?.summary;

  function toggle(value:number,selected:number[],setSelected:(values:number[])=>void){setSelected(selected.includes(value)?selected.filter(id=>id!==value):[...selected,value]);}
  async function downloadCatalogue(){
    setDownloading(true);setMessage("");
    try{
      await downloadAuthenticated("/exports/catalogue/xlsx/",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({period:period||null,form_ids:selectedForms,expected_submission_ids:selectedSubmissions})},"nca_data_form_catalogue.xlsx");
      setMessage("Catalogue downloaded successfully.");
    }catch(error){setMessage(error instanceof Error?error.message:"Download failed.");}finally{setDownloading(false);}
  }
  async function downloadApproved(format:"csv"|"pdf"){
    setDownloading(true);setMessage("");
    try{await downloadAuthenticated(`/exports/${format}/`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filters:{period}})},`nca_approved_data.${format}`);}catch(error){setMessage(error instanceof Error?error.message:"Download failed.");}finally{setDownloading(false);}
  }
  const selectedCount=selectedForms.length+selectedSubmissions.length;
  const summaryCards=useMemo(()=>summary?[{label:"Forms",value:summary.forms},{label:"Forms sent",value:summary.forms_sent},{label:"Submitted",value:summary.submitted},{label:"Approved",value:summary.approved},{label:"Providers",value:summary.providers}]:[],[summary]);

  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-[28px] font-semibold">Data & Form Catalogue</h1><p className="mt-1 text-sm text-[#737780]">Search all forms and reporting activity, review period summaries, and download governed catalogue extracts.</p></div><button onClick={downloadCatalogue} disabled={downloading||query.isLoading} className="inline-flex items-center gap-2 rounded-lg bg-[#001836] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><FileSpreadsheet size={16}/>{downloading?"Preparing…":selectedCount?`Download selected (${selectedCount})`:"Download full catalogue"}</button></div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{summaryCards.map(card=><div key={card.label} className="rounded-xl border bg-white p-4"><p className="text-xs uppercase text-[#737780]">{card.label}</p><p className="mt-1 text-2xl font-semibold">{card.value.toLocaleString()}</p></div>)}</div>
    <div className="rounded-2xl border bg-white p-5"><div className="grid gap-4 md:grid-cols-[1fr_280px]"><label className="relative"><span className="sr-only">Search catalogue</span><Search className="absolute left-3 top-3 text-[#737780]" size={17}/><input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search form, provider, period or submission ID" className="w-full rounded-lg border py-2.5 pl-10 pr-3 text-sm"/></label><select value={period} onChange={event=>{setPeriod(event.target.value);setSelectedForms([]);setSelectedSubmissions([]);}} className="rounded-lg border px-3 py-2.5 text-sm"><option value="">All reporting periods</option>{periods.map(item=><option key={item.id} value={item.id}>{item.name} · {item.frequency.replace("_"," ")}</option>)}</select></div><div className="mt-4 flex flex-wrap gap-2"><button onClick={()=>downloadApproved("csv")} disabled={downloading} className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold text-[#0066cc]"><Download size={15}/>Approved data CSV</button><button onClick={()=>downloadApproved("pdf")} disabled={downloading} className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold text-[#0066cc]"><Download size={15}/>Approved data PDF</button><p className="self-center text-xs text-[#737780]">Value exports contain NCA-approved submissions only. The catalogue summary includes all workflow stages.</p></div>{message&&<p className="mt-3 text-sm text-[#004999]">{message}</p>}</div>
    <div className="flex w-fit overflow-hidden rounded-lg border" role="tablist"><button role="tab" aria-selected={tab==="data"} onClick={()=>setTab("data")} className={`px-5 py-2 text-sm font-semibold ${tab==="data"?"bg-[#001836] text-white":"bg-white"}`}>Data & submissions</button><button role="tab" aria-selected={tab==="forms"} onClick={()=>setTab("forms")} className={`px-5 py-2 text-sm font-semibold ${tab==="forms"?"bg-[#001836] text-white":"bg-white"}`}>Forms</button></div>
    {query.isLoading&&<div className="rounded-xl bg-white p-10 text-sm text-[#737780]">Loading catalogue…</div>}
    {query.isError&&<div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">The catalogue could not be loaded. <button onClick={()=>query.refetch()} className="font-semibold underline">Retry</button></div>}
    {!query.isLoading&&!query.isError&&tab==="data"&&<div className="overflow-x-auto rounded-2xl border bg-white"><table className="w-full min-w-[1050px] text-left text-sm"><thead className="bg-[#f7f9fb] text-xs uppercase text-[#737780]"><tr><th className="p-4"></th><th className="p-4">Provider</th><th className="p-4">Form</th><th className="p-4">Period</th><th className="p-4">Status</th><th className="p-4">Completion</th><th className="p-4">Sent</th><th className="p-4">Due</th><th className="p-4">Submission ID</th><th className="p-4"></th></tr></thead><tbody className="divide-y">{submissions.map(item=><tr key={item.id}><td className="p-4"><input aria-label={`Select form task ${item.id}`} type="checkbox" checked={selectedSubmissions.includes(item.id)} onChange={()=>toggle(item.id,selectedSubmissions,setSelectedSubmissions)}/></td><td className="p-4 font-medium">{item.provider}</td><td className="p-4"><p className="font-medium">{item.form_name}</p><p className="text-xs text-[#737780]">{item.form_code}</p></td><td className="p-4">{item.period}</td><td className="p-4">{item.workflow_status.replaceAll("_"," ")}</td><td className="p-4">{Number(item.completion_pct).toFixed(0)}%</td><td className="p-4">{new Date(item.sent_at).toLocaleString()}</td><td className="p-4">{new Date(item.due_at).toLocaleDateString()}</td><td className="p-4 font-mono text-xs">{item.submission_reference||"Not submitted"}</td><td className="p-4">{item.submission_id&&<Link href={`/submissions/${item.submission_id}/review`} className="font-semibold text-[#0066cc]">View</Link>}</td></tr>)}</tbody></table>{!submissions.length&&<Empty text="No matching forms sent or submissions."/>}</div>}
    {!query.isLoading&&!query.isError&&tab==="forms"&&<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{forms.map(item=><article key={item.id} className="rounded-2xl border bg-white p-5"><div className="flex items-start justify-between"><div><p className="font-mono text-xs font-semibold text-[#0066cc]">{item.code} · v{item.version}</p><h2 className="mt-1 font-semibold">{item.name}</h2></div><input aria-label={`Select form ${item.code} version ${item.version}`} type="checkbox" checked={selectedForms.includes(item.id)} onChange={()=>toggle(item.id,selectedForms,setSelectedForms)}/></div><div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs"><span className="rounded bg-[#f7f9fb] p-2"><strong className="block text-base">{item.sections}</strong>Sections</span><span className="rounded bg-[#f7f9fb] p-2"><strong className="block text-base">{item.indicators}</strong>Indicators</span><span className="rounded bg-[#f7f9fb] p-2"><strong className="block text-base">{item.tables}</strong>Tables</span></div><div className="mt-4 flex items-center justify-between gap-3"><p className="text-xs text-[#737780]">{item.frequency.replace("_"," ")} · {item.status} · {item.approval_status.replace("_"," ")}</p><Link href={`/forms/${item.id}`} className="whitespace-nowrap text-xs font-semibold text-[#0066cc]">View form</Link></div></article>)}{!forms.length&&<div className="md:col-span-2 xl:col-span-3"><Empty text="No matching forms."/></div>}</div>}
  </div>;
}

function Empty({text}:{text:string}){return <div className="p-12 text-center text-sm text-[#737780]"><Database className="mx-auto mb-3"/>{text}</div>}

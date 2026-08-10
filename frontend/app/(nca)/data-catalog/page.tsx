"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Database, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { DataCatalog } from "@/lib/types";

export default function DataCatalogPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, error } = useQuery<DataCatalog>({ queryKey: ["data-catalog"], queryFn: () => api("/data-catalog/") });
  const forms = useMemo(() => (data?.forms ?? []).filter(f => `${f.name} ${f.code} ${f.description}`.toLowerCase().includes(search.toLowerCase())), [data, search]);
  return <div className="mx-auto max-w-6xl space-y-6">
    <div><p className="text-sm font-semibold text-[#0066cc]">DATA CATALOG</p><h1 className="mt-1 text-3xl font-semibold text-[#191c1e]">What data is available?</h1><p className="mt-2 text-sm text-[#737780]">Browse dataset descriptions only. Submitted values remain private until your request is approved.</p></div>
    <div className="relative max-w-xl"><Search className="absolute left-3 top-3 text-[#737780]" size={18}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search datasets" className="w-full rounded-xl border border-[#c3c6d0] bg-white py-2.5 pl-10 pr-4 text-sm"/></div>
    {isLoading && <div className="rounded-2xl bg-white p-8 text-sm text-[#737780]">Loading the catalog…</div>}
    {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">The catalog could not be loaded. Please refresh after the backend is running.</div>}
    {!isLoading && !error && forms.length === 0 && <div className="rounded-2xl bg-white p-10 text-center"><Database className="mx-auto text-[#737780]"/><p className="mt-3 font-medium">No matching datasets</p><p className="mt-1 text-sm text-[#737780]">Try another search, or ask an administrator to activate a form template.</p></div>}
    <div className="grid gap-4 md:grid-cols-2">{forms.map(form => {
      const fields=form.sections.reduce((n,s)=>n+s.fields.length+s.grids.reduce((m,g)=>m+g.columns.length,0),0);
      return <article key={form.id} className="rounded-2xl border border-[#e6e8ea] bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4"><div><span className="rounded-full bg-[#e8f1fb] px-2.5 py-1 text-xs font-semibold text-[#004999]">{form.code}</span><h2 className="mt-3 text-lg font-semibold">{form.name}</h2></div><Database className="text-[#0066cc]"/></div>
        <p className="mt-2 line-clamp-2 text-sm text-[#737780]">{form.description || "Regulatory reporting dataset"}</p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs text-[#43474f]"><span>{form.frequency.replace("_"," ")}</span><span>•</span><span>{form.sector}</span><span>•</span><span>{fields} fields</span><span>•</span><span>{form.available_period_ids.length} available periods</span></div>
        <Link href={`/data-requests/new?form=${form.id}`} className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#0066cc]">Request this data <ArrowRight size={15}/></Link>
      </article>})}</div>
  </div>;
}

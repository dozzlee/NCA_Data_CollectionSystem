"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SubmissionHistory } from "@/lib/types";
import { WorkflowBadge } from "@/components/ui/Badge";

export default function ProviderHistoryPage() {
  const query = useQuery({ queryKey: ["provider-history"], queryFn: () => api.get<SubmissionHistory[]>("/provider/history/") });
  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Submission History</h1><p className="text-[13px] text-[#737780]">Every version and decision for your organisation.</p></div>
    {(query.data ?? []).map((item) => <section key={item.id} className="overflow-hidden rounded-[14px] border border-[#e6e8ea] bg-white">
      <div className="flex items-center justify-between border-b border-[#eceef0] px-5 py-4"><div><h2 className="text-[14px] font-semibold">{item.form_name}</h2><p className="text-[12px] text-[#737780]">{item.period_name}</p></div><WorkflowBadge status={item.workflow_status} /></div>
      {item.versions.map((version) => <Link key={version.id} href={`/provider/approvals/${version.id}`} className="block border-b border-[#f0f1f2] px-5 py-3 hover:bg-[#f7f9fb]">
        <div className="flex justify-between"><p className="text-[13px] font-medium">Version {version.version}</p><p className="text-[11px] text-[#737780]">{version.submitted_at ? new Date(version.submitted_at).toLocaleString("en-GB") : "Draft"}</p></div>
        {!!version.events.length && <p className="mt-1 text-[11px] text-[#43474f]">{version.events[0].type.replaceAll("_", " ")} · {version.events[0].actor}</p>}
      </Link>)}
    </section>)}
    {!query.isLoading && !query.data?.length && <p className="rounded-[14px] border bg-white p-10 text-center text-[13px] text-[#737780]">No submission history yet.</p>}
  </div>;
}

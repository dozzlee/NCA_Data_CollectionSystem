"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission } from "@/lib/types";

export default function ProviderHistoryPage() {
  const { data, isLoading } = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["provider-history"],
    queryFn: () => api("/expected-submissions/?ordering=-period__due_at"),
  });

  // History = submissions that have been submitted or closed
  const history = (data?.results ?? []).filter(s =>
    ["SUBMITTED","UNDER_REVIEW","RESUBMITTED","APPROVED","REJECTED","ARCHIVED"].includes(s.workflow_status)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[28px] font-semibold text-[#191c1e]">Submission History</h1>
        <p className="mt-1 text-[14px] text-[#43474f]">
          All past submissions for your organisation — submitted, under review, approved, and rejected.
        </p>
      </div>

      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <table className="w-full text-left">
          <thead className="border-b border-[#eceef0] bg-[#f7f9fb]">
            <tr>
              {["Form","Period","Submitted","Status","Due State",""].map(h => (
                <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eceef0]">
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-5 py-4"><Skeleton className="h-3.5 w-full" /></td>
                  ))}</tr>
                ))
              : history.length === 0
              ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-[14px] text-[#737780]">
                    No submission history yet.
                  </td>
                </tr>
              )
              : history.map(s => (
                <tr key={s.id} className="hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-medium text-[#191c1e]">{s.form_name}</p>
                    <p className="text-[11px] text-[#737780] font-mono">{s.form_code}</p>
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{s.period_name}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#737780]">
                    {s.due_at ? new Date(s.due_at).toLocaleDateString("en-GB") : "—"}
                  </td>
                  <td className="px-5 py-3.5"><WorkflowBadge status={s.workflow_status} /></td>
                  <td className="px-5 py-3.5"><DueStateBadge state={s.due_state} /></td>
                  <td className="px-5 py-3.5">
                    <Link href={`/provider/submissions/${s.id}`}
                      className="text-[13px] font-medium text-[#0066cc] hover:underline">
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

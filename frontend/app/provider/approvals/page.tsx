"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ExpectedSubmission, PaginatedResponse } from "@/lib/types";
import { WorkflowBadge } from "@/components/ui/Badge";

export default function PendingApprovalsPage() {
  const query = useQuery({
    queryKey: ["pending-approvals"],
    queryFn: () => api.get<PaginatedResponse<ExpectedSubmission>>("/expected-submissions/?workflow_status=PENDING_APPROVAL"),
  });
  const items = query.data?.results ?? [];
  return (
    <div className="space-y-6">
      <div><h1 className="text-[28px] font-semibold">Pending Approval</h1><p className="text-[13px] text-[#737780]">Review submissions before they are sent to NCA.</p></div>
      <div className="overflow-hidden rounded-[14px] border border-[#e6e8ea] bg-white">
        {!items.length ? <p className="p-10 text-center text-[13px] text-[#737780]">No submissions are awaiting approval.</p> :
          items.map((item) => (
            <Link key={item.id} href={`/provider/approvals/${item.latest_submission_id}`} className="flex items-center justify-between border-b border-[#eceef0] px-5 py-4 hover:bg-[#f7f9fb]">
              <div><p className="text-[14px] font-semibold">{item.form_name}</p><p className="text-[12px] text-[#737780]">{item.period_name} · Version {item.latest_version}</p></div>
              <WorkflowBadge status={item.workflow_status} />
            </Link>
          ))}
      </div>
    </div>
  );
}

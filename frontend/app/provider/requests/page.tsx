"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { EditRequest, PaginatedResponse, ExpectedSubmission } from "@/lib/types";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function ProviderRequestsPage() {
  const user = useCurrentUser().data;
  const qc = useQueryClient();
  const [submission, setSubmission] = useState("");
  const [reason, setReason] = useState("");
  const requestsQ = useQuery({ queryKey: ["edit-requests"], queryFn: () => api.get<PaginatedResponse<EditRequest>>("/edit-requests/") });
  const eligibleQ = useQuery({ queryKey: ["edit-request-eligible"], queryFn: () => api.get<PaginatedResponse<ExpectedSubmission>>("/expected-submissions/") });
  const create = useMutation({
    mutationFn: () => api.post("/edit-requests/", { submission: Number(submission), reason }),
    onSuccess: () => { setReason(""); setSubmission(""); qc.invalidateQueries({ queryKey: ["edit-requests"] }); },
  });
  const eligible = (eligibleQ.data?.results ?? []).filter((item) => item.latest_submission_id && ["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "REJECTED"].includes(item.workflow_status));
  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Edit Requests</h1><p className="text-[13px] text-[#737780]">Request NCA approval before changing an official submission.</p></div>
    {user?.role === "PROVIDER_APPROVER" && <div className="rounded-[14px] border bg-white p-5">
      <h2 className="text-[15px] font-semibold">New request</h2>
      <select value={submission} onChange={(event) => setSubmission(event.target.value)} className="mt-3 w-full rounded-[8px] border p-2 text-[13px]">
        <option value="">Select a submitted form</option>{eligible.map((item) => <option key={item.id} value={item.latest_submission_id!}>{item.form_name} — {item.period_name}</option>)}
      </select>
      <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain why the official submission needs to change" rows={3} className="mt-3 w-full rounded-[8px] border p-3 text-[13px]" />
      <button disabled={!submission || !reason.trim() || create.isPending} onClick={() => create.mutate()} className="mt-3 rounded-[8px] bg-[#002d5b] px-4 py-2 text-[13px] font-semibold text-white disabled:opacity-40">Send request</button>
    </div>}
    <div className="overflow-hidden rounded-[14px] border bg-white">{(requestsQ.data?.results ?? []).map((item) => <div key={item.id} className="border-b px-5 py-4">
      <div className="flex justify-between"><div><p className="text-[13px] font-semibold">{item.form_name}</p><p className="text-[11px] text-[#737780]">{item.period_name} · Requested by {item.requested_by_name}</p></div><span className="text-[11px] font-bold">{item.status}</span></div>
      <p className="mt-2 text-[12px]">{item.reason}</p>{item.decision_note && <p className="mt-1 text-[11px] text-[#43474f]">NCA: {item.decision_note}</p>}
    </div>)}</div>
  </div>;
}

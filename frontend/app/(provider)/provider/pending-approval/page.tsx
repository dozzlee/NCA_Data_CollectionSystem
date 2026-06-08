"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { ExpectedSubmission } from "@/lib/types";

function formatDue(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { day:"numeric", month:"short", year:"numeric" });
}

export default function PendingApprovalPage() {
  const { toast } = useToast();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["provider-pending-approval"],
    queryFn: () => api("/expected-submissions/?workflow_status=PENDING_APPROVAL&ordering=period__due_at"),
  });

  const submissions = data?.results ?? [];

  const submitToNCA = useMutation({
    mutationFn: (submissionId: number) =>
      api(`/submissions/${submissionId}/official-submit/`, { method: "POST" }),
    onSuccess: () => {
      toast("Submission officially sent to NCA.", "success");
      qc.invalidateQueries({ queryKey: ["provider-pending-approval"] });
    },
    onError: () => toast("Failed to submit. Please try again.", "error"),
  });

  const returnToDraft = useMutation({
    mutationFn: (submissionId: number) =>
      api(`/submissions/${submissionId}/return-to-draft/`, { method: "POST" }),
    onSuccess: () => {
      toast("Returned to data entry.", "info");
      qc.invalidateQueries({ queryKey: ["provider-pending-approval"] });
    },
    onError: () => toast("Failed to return. Please try again.", "error"),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[28px] font-semibold text-[#191c1e]">Pending Your Approval</h1>
        <p className="mt-1 text-[14px] text-[#43474f]">
          These submissions have been completed by your data entry team and are awaiting your review before official submission to NCA.
        </p>
      </div>

      {!isLoading && submissions.length === 0 && (
        <div className="rounded-[16px] border-2 border-dashed border-[#c3c6d0] py-16 text-center">
          <p className="text-[20px] mb-1">✓</p>
          <p className="text-[14px] font-medium text-[#191c1e]">No submissions pending your approval</p>
          <p className="text-[13px] text-[#737780] mt-1">Your data entry team hasn't submitted anything yet.</p>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-[12px]" />)}
        </div>
      ) : (
        <div className="space-y-4">
          {submissions.map(s => (
            <div key={s.id} className="rounded-[16px] border border-[#eceef0] bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <WorkflowBadge status={s.workflow_status} />
                    <DueStateBadge state={s.due_state} />
                  </div>
                  <h3 className="text-[15px] font-semibold text-[#191c1e]">{s.form_name}</h3>
                  <p className="text-[13px] text-[#43474f] mt-0.5">{s.period_name} · Due {formatDue(s.due_at)}</p>
                </div>

                <div className="flex gap-2 shrink-0">
                  <Link href={`/provider/submissions/${s.id}`}
                    className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] font-medium text-[#43474f] hover:bg-[#f2f4f6]">
                    Review Form
                  </Link>
                  <button
                    onClick={() => {
                      if (s.latest_submission_id) returnToDraft.mutate(s.latest_submission_id);
                    }}
                    disabled={returnToDraft.isPending}
                    className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] font-medium text-[#43474f] hover:bg-[#f2f4f6] disabled:opacity-50">
                    Return to Data Entry
                  </button>
                  <button
                    onClick={() => {
                      if (s.latest_submission_id && confirm(`Officially submit "${s.form_name}" to NCA? This cannot be undone.`)) {
                        submitToNCA.mutate(s.latest_submission_id);
                      }
                    }}
                    disabled={submitToNCA.isPending}
                    className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
                    ✓ Submit to NCA
                  </button>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-[#eceef0] flex items-center gap-2 text-[12px] text-[#737780]">
                <span>Form code: <span className="font-mono font-semibold text-[#43474f]">{s.form_code}</span></span>
                <span>·</span>
                <span>Provider: <span className="font-medium text-[#43474f]">{s.provider_name}</span></span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-[12px] bg-[#f7f9fb] border border-[#eceef0] px-5 py-4 text-[13px] text-[#43474f]">
        <p className="font-semibold text-[#191c1e] mb-1">As Provider Approver, you are responsible for:</p>
        <ul className="list-disc list-inside space-y-0.5 text-[12px]">
          <li>Reviewing all data entered by your data entry team for accuracy and completeness</li>
          <li>Returning submissions that need corrections before they reach NCA</li>
          <li>Officially submitting accurate, complete returns to NCA on behalf of your organisation</li>
        </ul>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FormTemplate, ExpectedSubmission, WorkflowStatus } from "@/lib/types";
import { WorkflowBadge } from "@/components/ui/Badge";
import { useCurrentUser } from "@/hooks/useCurrentUser";

interface SubmissionDetail {
  id: number; expected: number; version: number; completion_pct: string;
  form_name: string; form_code: string; period_name: string; workflow_status: WorkflowStatus;
  submitted_by_email: string | null; submitted_at: string | null;
}

export default function ApprovalWorkspacePage() {
  const submissionId = Number(useParams().id);
  const router = useRouter();
  const qc = useQueryClient();
  const user = useCurrentUser().data;
  const [reason, setReason] = useState("");
  const submissionQ = useQuery({ queryKey: ["submission", submissionId], queryFn: () => api.get<SubmissionDetail>(`/submissions/${submissionId}/`) });
  const expectedQ = useQuery({
    queryKey: ["expected-for-version", submissionQ.data?.expected],
    queryFn: () => api.get<ExpectedSubmission>(`/expected-submissions/${submissionQ.data!.expected}/`),
    enabled: !!submissionQ.data,
  });
  const formQ = useQuery({
    queryKey: ["form-template", expectedQ.data?.form_template],
    queryFn: () => api.get<FormTemplate & { sections: Array<{ id: number; section_code: string; title: string }> }>(`/form-templates/${expectedQ.data!.form_template}/`),
    enabled: !!expectedQ.data,
  });
  const valuesQ = useQuery({
    queryKey: ["approval-values", submissionId, formQ.data?.sections],
    queryFn: async () => {
      const groups = await Promise.all((formQ.data?.sections ?? []).map(async (section) => ({
        section,
        values: await api.get<Array<{ id: number; value: string; value_status: string; explanation: string }>>(`/submissions/${submissionId}/sections/${section.section_code}/values/`),
      })));
      return groups;
    },
    enabled: !!formQ.data,
  });
  const action = useMutation({
    mutationFn: (kind: "return" | "submit") => kind === "return"
      ? api.post(`/submissions/${submissionId}/return-to-draft/`, { reason })
      : api.post(`/submissions/${submissionId}/official-submit/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pending-approvals"] });
      router.push("/provider/dashboard");
    },
  });
  const submission = submissionQ.data;
  if (!submission) return <p className="text-[13px] text-[#737780]">Loading submission…</p>;
  const canApprove = user?.role === "PROVIDER_APPROVER" && submission.workflow_status === "PENDING_APPROVAL";
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div><div className="flex items-center gap-2"><h1 className="text-[24px] font-semibold">{submission.form_name}</h1><WorkflowBadge status={submission.workflow_status} /></div>
          <p className="text-[13px] text-[#737780]">{submission.period_name} · Version {submission.version} · {submission.completion_pct}% complete</p></div>
      </div>
      {(valuesQ.data ?? []).map(({ section, values }) => (
        <section key={section.id} className="rounded-[14px] border border-[#e6e8ea] bg-white p-5">
          <h2 className="mb-3 text-[16px] font-semibold">{section.title}</h2>
          {!values.length ? <p className="text-[12px] text-[#737780]">No values entered.</p> :
            values.map((value) => <div key={value.id} className="flex justify-between border-t border-[#f0f1f2] py-2 text-[12px]"><span className="text-[#737780]">{value.value_status}</span><span className="max-w-[70%] text-right">{value.value || "—"}</span></div>)}
        </section>
      ))}
      {canApprove && (
        <div className="rounded-[14px] border border-[#dfe2e6] bg-white p-5">
          <label className="text-[12px] font-semibold">Reason when returning</label>
          <textarea value={reason} onChange={(event) => setReason(event.target.value)} className="mt-2 w-full rounded-[8px] border border-[#c3c6d0] p-3 text-[13px]" rows={3} />
          <div className="mt-3 flex justify-end gap-2">
            <button disabled={!reason.trim() || action.isPending} onClick={() => action.mutate("return")} className="rounded-[8px] border border-[#E31937] px-4 py-2 text-[13px] font-semibold text-[#E31937] disabled:opacity-40">Return for correction</button>
            <button disabled={action.isPending} onClick={() => action.mutate("submit")} className="rounded-[8px] bg-[#1f7a4d] px-4 py-2 text-[13px] font-semibold text-white">Submit to NCA</button>
          </div>
        </div>
      )}
    </div>
  );
}

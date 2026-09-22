import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FormTemplate, FormSection, ExpectedSubmission } from "@/lib/types";

type FormTemplateDetail = FormTemplate & { sections: FormSection[] };

interface Submission {
  id: number;
  submission_reference: string;
  expected: number;
  version: number;
  completion_pct: string;
  workflow_status: string;
  form_code: string;
  form_name: string;
  period_name: string;
  kmz_required: boolean;
  submitted_at: string | null;
  revision: number;
  last_edited_by: string | null;
  last_edited_by_name: string | null;
  last_edited_at: string | null;
  receipt_reference: string | null;
}

interface SectionCompletion {
  section_code: string;
  title: string;
  required: number;
  provided: number;
  complete: boolean;
}

interface CompletionData {
  completion_pct: number;
  can_submit: boolean;
  missing_required_count: number;
  missing_indicator_count: number;
  missing_by_type: Record<string, number>;
  completeness_warnings: {
    code: string;
    type: string;
    id: number | string;
    section_code: string;
    label: string;
  }[];
  blocking_issues: {
    code: string;
    type: string;
    id: number | string;
    section_code: string;
    label: string;
  }[];
  sections: SectionCompletion[];
  transition_ready: boolean;
  open_correction_item_count: number;
  open_correction_items: Array<{ id:number; stage:string; target_type:string; target_id:string; instruction:string }>;
  warning_count: number;
  validation_issues: Array<{ id:number; severity:string; target_type:string; target_id:string; code:string; message:string; details:Record<string, unknown> }>;
}

interface SubmissionValue {
  id?: number;
  field?: number | null;
  grid?: number | null;
  grid_row_id?: string;
  grid_column?: number | null;
  value: string;
  value_status: string;
  explanation?: string;
  value_source?: "MANUAL" | "EXCEL_IMPORT" | "SYSTEM";
  source_reference?: string;
}

export function useFormTemplate(id: number) {
  return useQuery({
    queryKey: ["form-template", id],
    queryFn: () => api.get<FormTemplateDetail>(`/form-templates/${id}/`),
    enabled: !!id,
  });
}

export function useExpectedSubmission(id: number) {
  return useQuery({
    queryKey: ["expected-submission", id],
    queryFn: () => api.get<ExpectedSubmission>(`/expected-submissions/${id}/`),
    enabled: !!id,
  });
}

export function useSubmission(id: number | null) {
  return useQuery({
    queryKey: ["submission", id],
    queryFn: () => api.get<Submission>(`/submissions/${id}/`),
    enabled: !!id,
  });
}

export function useSubmissionCompletion(submissionId: number | null) {
  return useQuery({
    queryKey: ["submission-completion", submissionId],
    queryFn: () => api.get<CompletionData>(`/submissions/${submissionId}/completion/`),
    enabled: !!submissionId,
    refetchInterval: false,
  });
}

export function useSectionValues(submissionId: number | null, sectionCode: string) {
  return useQuery({
    queryKey: ["section-values", submissionId, sectionCode],
    queryFn: () => api.get<SubmissionValue[]>(`/submissions/${submissionId}/sections/${sectionCode}/values/`),
    enabled: !!submissionId && !!sectionCode,
  });
}

export function useSaveSectionValues(submissionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionCode, values, revision, clientSaveId, changeVersion }: { sectionCode: string; values: SubmissionValue[]; revision?: number; clientSaveId: string; changeVersion: number }) =>
      api.put<{ saved: number; completion_pct: number; revision: number; client_save_id:string; base_revision:number; resulting_revision:number; persisted_change_version:number; replayed:boolean; last_edited_by_name:string; last_edited_at:string }>(
        `/submissions/${submissionId}/sections/${sectionCode}/values/`,
        { values, revision, client_save_id:clientSaveId, change_version:changeVersion }
      ),
    onSuccess: (response, { sectionCode }) => {
      qc.invalidateQueries({ queryKey: ["section-values", submissionId, sectionCode] });
      qc.invalidateQueries({ queryKey: ["submission-completion", submissionId] });
      qc.setQueryData<Submission>(["submission", submissionId], (current) =>
        current ? { ...current, revision: response.revision, last_edited_by_name:response.last_edited_by_name, last_edited_at:response.last_edited_at } : current
      );
    },
  });
}

export function useStartSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (expectedId: number) =>
      api.post<Submission>(`/expected-submissions/${expectedId}/start/`),
    onSuccess: (_response, expectedId) => {
      qc.invalidateQueries({ queryKey: ["expected-submissions"] });
      qc.invalidateQueries({ queryKey: ["expected-submission", expectedId] });
      qc.invalidateQueries({ queryKey: ["provider-workspace"] });
      qc.invalidateQueries({ queryKey: ["provider-workspace-summary"] });
      qc.invalidateQueries({ queryKey: ["submission-notifications"] });
      qc.invalidateQueries({ queryKey: ["submission-notification-summary"] });
    },
  });
}

export function useSubmitForApproval(submissionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{event_id:number;internal_notification_created:boolean}>(`/submissions/${submissionId}/submit-for-approval/`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["submission", submissionId] });
      qc.invalidateQueries({ queryKey: ["provider-review-data", submissionId] });
      qc.invalidateQueries({ queryKey: ["submission-completion", submissionId] });
      qc.invalidateQueries({ queryKey: ["expected-submissions"] });
      qc.invalidateQueries({ queryKey: ["provider-workspace"] });
      qc.invalidateQueries({ queryKey: ["provider-workspace-summary"] });
      qc.invalidateQueries({ queryKey: ["provider-approval-queue"] });
      qc.invalidateQueries({ queryKey: ["submission-notifications"] });
      qc.invalidateQueries({ queryKey: ["submission-notification-summary"] });
      qc.invalidateQueries({ queryKey: ["provider-period-forms"] });
    },
  });
}

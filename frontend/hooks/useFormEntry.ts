import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FormTemplate, FormSection, ExpectedSubmission } from "@/lib/types";

type FormTemplateDetail = FormTemplate & { sections: FormSection[] };

interface Submission {
  id: number;
  expected: number;
  version: number;
  completion_pct: string;
  workflow_status: string;
  form_code: string;
  form_name: string;
  period_name: string;
  kmz_required: boolean;
  submitted_at: string | null;
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
  sections: SectionCompletion[];
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
    mutationFn: ({ sectionCode, values }: { sectionCode: string; values: SubmissionValue[] }) =>
      api.put<{ saved: number; completion_pct: number }>(
        `/submissions/${submissionId}/sections/${sectionCode}/values/`,
        { values }
      ),
    onSuccess: (_, { sectionCode }) => {
      qc.invalidateQueries({ queryKey: ["section-values", submissionId, sectionCode] });
      qc.invalidateQueries({ queryKey: ["submission-completion", submissionId] });
    },
  });
}

export function useStartSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (expectedId: number) =>
      api.post<Submission>(`/expected-submissions/${expectedId}/start/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expected-submissions"] });
    },
  });
}

export function useSubmitForApproval(submissionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/submissions/${submissionId}/submit-for-approval/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["submission", submissionId] });
      qc.invalidateQueries({ queryKey: ["expected-submissions"] });
    },
  });
}

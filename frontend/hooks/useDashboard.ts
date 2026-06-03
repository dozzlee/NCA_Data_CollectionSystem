import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  DashboardSummary,
  StatusDonutItem,
  CategoryCompletionItem,
  OverdueByFormItem,
  PaginatedResponse,
  ExpectedSubmission,
} from "@/lib/types";

export function useDashboardSummary(periodId?: number) {
  const params = periodId ? `?period_id=${periodId}` : "";
  return useQuery({
    queryKey: ["dashboard-summary", periodId],
    queryFn: () => api.get<DashboardSummary>(`/dashboard/summary/${params}`),
  });
}

export function useStatusDonut(periodId?: number) {
  const params = periodId ? `?period_id=${periodId}` : "";
  return useQuery({
    queryKey: ["chart-status-donut", periodId],
    queryFn: () => api.get<StatusDonutItem[]>(`/dashboard/charts/status-donut/${params}`),
  });
}

export function useCategoryCompletion(periodId?: number) {
  const params = periodId ? `?period_id=${periodId}` : "";
  return useQuery({
    queryKey: ["chart-category-completion", periodId],
    queryFn: () => api.get<CategoryCompletionItem[]>(`/dashboard/charts/category-completion/${params}`),
  });
}

export function useSubmissionTrend() {
  return useQuery({
    queryKey: ["chart-submission-trend"],
    queryFn: () => api.get<{ month: string; count: number }[]>(`/dashboard/charts/submission-trend/`),
  });
}

export function useOverdueByForm() {
  return useQuery({
    queryKey: ["chart-overdue-by-form"],
    queryFn: () => api.get<OverdueByFormItem[]>(`/dashboard/charts/overdue-by-form/`),
  });
}

export function useExpectedSubmissions(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(params).toString();
  return useQuery({
    queryKey: ["expected-submissions", params],
    queryFn: () =>
      api.get<PaginatedResponse<ExpectedSubmission>>(
        `/expected-submissions/${qs ? `?${qs}` : ""}`
      ),
  });
}

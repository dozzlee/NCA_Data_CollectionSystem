"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { SectionStepper } from "@/components/forms/SectionStepper";
import { FieldRenderer } from "@/components/forms/FieldRenderer";
import { GridRenderer } from "@/components/forms/GridRenderer";
import { KMZUploadPanel } from "@/components/forms/KMZUploadPanel";
import { ExcelBackupPanel } from "@/components/forms/ExcelBackupPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { WorkflowBadge } from "@/components/ui/Badge";
import {
  useExpectedSubmission,
  useSubmission,
  useSubmissionCompletion,
  useSectionValues,
  useSaveSectionValues,
  useStartSubmission,
  useSubmitForApproval,
  useFormTemplate,
} from "@/hooks/useFormEntry";
import { api, ApiError } from "@/lib/api";
import { Save, Send, ChevronRight, ChevronLeft, AlertTriangle } from "lucide-react";
import type { ExpectedSubmission, FormSection, FieldStatus } from "@/lib/types";

// ─── Local value state for one section ───────────────────────────────────────

type FieldValues = Record<string, { value: string; status: FieldStatus | ""; explanation: string }>;
type GridCellValue = { grid_row_id: string; grid_column_id: number; value: string; value_status: FieldStatus | ""; explanation?: string };
type TimelineEvent = { id:number; event_type:string; message:string; from_status:string; to_status:string; actor_name:string|null; created_at:string };

function useSectionFieldState(
  sectionFields: FormSection["fields"],
  serverValues: { field?: number | null; value: string; value_status: string; explanation?: string }[] | undefined
) {
  const [fieldValues, setFieldValues] = useState<FieldValues>({});

  useEffect(() => {
    if (!serverValues) return;
    const init: FieldValues = {};
    sectionFields?.forEach((f) => {
      const sv = serverValues.find((v) => v.field === f.id);
      init[f.id] = {
        value: sv?.value ?? "",
        status: (sv?.value_status as FieldStatus) ?? "",
        explanation: sv?.explanation ?? "",
      };
    });
    setFieldValues(init);
  }, [serverValues, sectionFields]);

  return [fieldValues, setFieldValues] as const;
}

// ─── Section Content ──────────────────────────────────────────────────────────

function SectionContent({
  section,
  submissionId,
  isEditable,
  kmzRequired,
  submissionRevision,
}: {
  section: FormSection;
  submissionId: number;
  isEditable: boolean;
  kmzRequired: boolean;
  submissionRevision: number;
}) {
  const serverValues = useSectionValues(submissionId, section.section_code);
  const saveMutation = useSaveSectionValues(submissionId);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<"saved" | "error" | null>(null);

  const [fieldValues, setFieldValues] = useSectionFieldState(section.fields, serverValues.data ?? []);
  const [gridValues, setGridValues] = useState<Record<number, GridCellValue[]>>({});
  const [excelUploads, setExcelUploads] = useState<any[]>([]);
  const [kmzUploads, setKmzUploads] = useState<any[]>([]);
  const queryClient = useQueryClient();

  useEffect(() => {
    const fetchExcelUploads = async () => {
      try {
        setExcelUploads(await api.get<any[]>(`/submissions/${submissionId}/excel-backups/`));
      } catch (err) {
        console.error("Failed to fetch Excel uploads:", err);
      }
    };
    if (submissionId) fetchExcelUploads();
  }, [submissionId]);

  useEffect(() => {
    const grouped: Record<number, GridCellValue[]> = {};
    for (const value of serverValues.data ?? []) {
      if (!value.grid || !value.grid_column) continue;
      (grouped[value.grid] ??= []).push({
        grid_row_id: value.grid_row_id ?? "",
        grid_column_id: value.grid_column,
        value: value.value,
        value_status: value.value_status as FieldStatus,
        explanation: value.explanation ?? "",
      });
    }
    setGridValues(grouped);
  }, [serverValues.data]);

  useEffect(() => {
    if (!kmzRequired) return;
    api.get<any[]>(`/submissions/${submissionId}/kmz-uploads/`)
      .then(setKmzUploads)
      .catch((err) => console.error("Failed to fetch KMZ uploads:", err));
  }, [kmzRequired, submissionId]);

  function handleFieldChange(fieldId: number, value: string, status: FieldStatus | "", explanation: string) {
    setFieldValues((prev) => ({ ...prev, [fieldId]: { value, status, explanation } }));
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    try {
      const fieldPayload = Object.entries(fieldValues).map(([fid, v]) => ({
        field: Number(fid),
        value: v.value,
        value_status: v.status || (v.value ? "PROVIDED" : "MISSING"),
        explanation: v.explanation,
      }));
      const gridPayload = Object.entries(gridValues).flatMap(([gid, rows]) =>
        rows.map((r) => ({ grid: Number(gid), grid_row_id: r.grid_row_id, grid_column: r.grid_column_id, value: r.value, value_status: r.value_status, explanation: r.explanation ?? "" }))
      );
      await saveMutation.mutateAsync({ sectionCode: section.section_code, values: [...fieldPayload, ...gridPayload], revision: submissionRevision });
      setDirty(false);
      setSaveMsg("saved");
      setTimeout(() => setSaveMsg(null), 2000);
    } catch {
      setSaveMsg("error");
    } finally {
      setSaving(false);
    }
  }

  async function handleKMZUpload(file: File, requirementId: number) {
    const form = new FormData();
    form.append("file", file);
    form.append("requirement_id", String(requirementId));
    await api.upload(`/submissions/${submissionId}/kmz-uploads/`, form);
    setKmzUploads(await api.get<any[]>(`/submissions/${submissionId}/kmz-uploads/`));
    queryClient.invalidateQueries({ queryKey: ["submission-completion", submissionId] });
  }

  async function handleExcelUpload(file: File) {
    const form = new FormData();
    form.append("file", file);
    await api.upload(`/submissions/${submissionId}/excel-backups/upload/`, form);
    setExcelUploads(await api.get<any[]>(`/submissions/${submissionId}/excel-backups/`));
  }

  if (serverValues.isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Section header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>
            {section.title}
          </h2>
          {section.instructions && (
            <p className="mt-1 text-[13px] text-[#43474f] leading-relaxed max-w-2xl">{section.instructions}</p>
          )}
        </div>

        {isEditable && (
          <div className="flex items-center gap-2 shrink-0">
            {saveMsg === "saved" && (
              <span className="text-[12px] text-[#1f7a4d] font-medium">Saved</span>
            )}
            {saveMsg === "error" && (
              <span className="text-[12px] text-[#E31937] font-medium">Save failed</span>
            )}
            {dirty && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 rounded-[8px] bg-[#002d5b] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#001836] disabled:opacity-60 transition-colors"
              >
                <Save size={13} />
                {saving ? "Saving…" : "Save progress"}
              </button>
            )}
          </div>
        )}
      </div>

      {/* KMZ upload panel — only for fibre forms AND sections that require it */}
      {kmzRequired && section.kmz_upload_required && section.kmz_requirements.map((requirement) => (
        <KMZUploadPanel
          key={requirement.id}
          submissionId={submissionId}
          requirementId={requirement.id}
          category={requirement.category.split("_").join(" ")}
          description={requirement.description}
          isRequired={requirement.is_required}
          uploads={kmzUploads.filter((upload) => upload.requirement_id === requirement.id)}
          onUpload={handleKMZUpload}
          disabled={!isEditable}
        />
      ))}

      {/* Scalar fields */}
      {section.fields.length > 0 && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {section.fields.map((field) => {
            const fv = fieldValues[field.id] ?? { value: "", status: "", explanation: "" };
            return (
              <div key={field.id} className={field.field_type === "textarea" || field.field_type === "declaration" ? "md:col-span-2" : ""}>
                <FieldRenderer
                  field={field}
                  value={fv.value}
                  valueStatus={fv.status}
                  explanation={fv.explanation}
                  onChange={(v, s, e) => handleFieldChange(field.id, v, s, e)}
                  disabled={!isEditable}
                  allFieldValues={Object.fromEntries(
                    Object.entries(fieldValues).map(([k, v]) => [k, { value: v.value }])
                  )}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Grids */}
      {section.grids.map((grid) => (
        <div key={grid.id}>
          <GridRenderer
            grid={grid}
            values={gridValues[grid.id] ?? []}
            onChange={(vals) => {
              setGridValues((prev) => ({ ...prev, [grid.id]: vals }));
              setDirty(true);
            }}
            disabled={!isEditable}
          />
        </div>
      ))}

      {/* Excel backup panel — available for all forms */}
      {isEditable && (
        <ExcelBackupPanel
          submissionId={submissionId}
          uploads={excelUploads}
          onUpload={handleExcelUpload}
          disabled={!isEditable}
          description="Upload an Excel file as a backup. This is stored for source control only and not analyzed."
        />
      )}

      {/* Auto-save prompt when dirty */}
      {dirty && isEditable && (
        <div className="flex items-center gap-2 rounded-[8px] border border-[#ffd100] bg-[#fff3bf]/60 px-3 py-2 text-[12px] text-[#7a5c00]">
          <AlertTriangle size={12} />
          You have unsaved changes. Click &quot;Save progress&quot; to avoid losing data.
        </div>
      )}
    </div>
  );
}

// ─── Main Form Entry Page ─────────────────────────────────────────────────────

export default function FormEntryPage() {
  const params = useParams();
  const expectedId = Number(params.id);

  // Current user — to gate actions by role
  const { data: currentUser } = useQuery<import("@/lib/types").User>({
    queryKey: ["me"],
    queryFn: () => api("/auth/me/"),
    staleTime: 5 * 60 * 1000,
  });
  const isApprover = currentUser?.role === "PROVIDER_APPROVER";
  const isDataEntry = currentUser?.role === "PROVIDER_DATA_ENTRY";

  const expectedQ = useExpectedSubmission(expectedId);
  const expected = expectedQ.data;

  const periodFormsQ = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["provider-period-forms", expected?.period],
    queryFn: () => api(`/expected-submissions/?period=${expected?.period}&ordering=form_template`),
    enabled: !!expected?.period,
  });

  // Get or create submission
  const latestSubmissionId = expected ? (expected as { latest_submission_id?: number }).latest_submission_id ?? null : null;
  const submissionQ = useSubmission(latestSubmissionId);
  const submission = submissionQ.data;
  const timelineQ = useQuery<TimelineEvent[]>({
    queryKey: ["submission-timeline", latestSubmissionId],
    queryFn: () => api(`/submissions/${latestSubmissionId}/timeline/`),
    enabled: Boolean(latestSubmissionId),
  });

  const formQ = useFormTemplate(expected?.form_template ?? 0);
  const form = formQ.data;

  const completionQ = useSubmissionCompletion(submission?.id ?? null);
  const completion = completionQ.data;

  const startMutation = useStartSubmission();
  const submitMutation = useSubmitForApproval(submission?.id ?? 0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionSection, setCorrectionSection] = useState("");

  const sections = useMemo(() => form?.sections ?? [], [form?.sections]);
  const [activeSection, setActiveSection] = useState<string>("");

  useEffect(() => {
    if (sections.length && !activeSection) {
      setActiveSection(sections[0].section_code);
    }
  }, [sections, activeSection]);

  const currentSectionIndex = sections.findIndex((s) => s.section_code === activeSection);
  const currentSection = sections[currentSectionIndex];
  const periodForms = periodFormsQ.data?.results ?? [];

  const isEditable = Boolean(
    isDataEntry
    && ["DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"].includes(expected?.workflow_status ?? "")
  );

  async function handleStart() {
    if (!expectedId) return;
    await startMutation.mutateAsync(expectedId);
    expectedQ.refetch();
  }

  async function handleSubmitForApproval() {
    setSubmitError(null);
    try {
      await submitMutation.mutateAsync();
      expectedQ.refetch();
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : "Submission failed. Please try again.");
      completionQ.refetch();
    }
  }

  if (expectedQ.isLoading || formQ.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="flex gap-6">
          <Skeleton className="h-[500px] w-[240px]" />
          <Skeleton className="h-[500px] flex-1" />
        </div>
      </div>
    );
  }

  if (!expected || !form) {
    return <p className="text-[13px] text-[#737780]">Submission not found.</p>;
  }

  // Not yet started
  if (expected.workflow_status === "NOT_STARTED") {
    return (
      <div className="space-y-4">
        <Link href="/provider/dashboard"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
          <ChevronLeft size={14} /> Back to My Forms
        </Link>
        <div className="flex flex-col items-center justify-center min-h-[360px] text-center">
        <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-8 max-w-md space-y-4"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.06)" }}>
          <div>
            <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{form.form_code}</p>
            <h1 className="text-[20px] font-semibold text-[#191c1e] mt-1">{form.name}</h1>
            <p className="text-[13px] text-[#43474f] mt-1">{expected.period_name}</p>
          </div>
          <p className="text-[13px] text-[#43474f]">
            This form has {sections.length} sections. You can save your progress at any time and return later.
          </p>
          {isDataEntry ? (
            <button
              onClick={handleStart}
              disabled={startMutation.isPending}
              className="w-full rounded-[8px] bg-[#002d5b] px-4 py-2.5 text-[14px] font-semibold text-white hover:bg-[#001836] disabled:opacity-60 transition-colors"
            >
              {startMutation.isPending ? "Starting…" : "Start form"}
            </button>
          ) : (
            <p className="rounded-[8px] bg-[#f2f4f6] px-4 py-3 text-[12px] text-[#43474f]">
              This form must be started by a Provider Data Entry user before it can be reviewed.
            </p>
          )}
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Back navigation */}
      <Link href="/provider/dashboard"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
        <ChevronLeft size={14} /> Back to My Forms
      </Link>

      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{form.form_code}</p>
            <WorkflowBadge status={expected.workflow_status} />
          </div>
          <h1 className="text-[20px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>
            {form.name}
          </h1>
          <p className="text-[13px] text-[#737780] mt-0.5">{expected.period_name}</p>
        </div>

        <div className="flex gap-2 shrink-0">
          {/* DATA ENTRY: can submit draft to approver */}
          {isDataEntry && ["DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"].includes(expected.workflow_status) && (
            <button
              onClick={handleSubmitForApproval}
              disabled={submitMutation.isPending || !completion?.can_submit}
              className="flex items-center gap-2 rounded-[8px] bg-[#1f7a4d] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#185e3b] disabled:opacity-50 transition-colors"
              title="Complete all required fields before submitting to your approver"
            >
              <Send size={13} />
              {submitMutation.isPending ? "Submitting…" : "Submit to Approver"}
            </button>
          )}
          {/* APPROVER: can return to data entry or officially submit to NCA */}
          {isApprover && ["PENDING_APPROVAL", "PROVIDER_RESUBMITTED"].includes(expected.workflow_status) && (
            <>
              <button
                onClick={() => {
                  setCorrectionSection(activeSection || sections[0]?.section_code || "");
                  setCorrectionOpen(true);
                }}
                className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] px-4 py-2.5 text-[13px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors"
              >
                Return to Data Entry
              </button>
              <button
                onClick={async () => {
                  await api(`/submissions/${submission?.id}/official-submit/`, { method: "POST" });
                  expectedQ.refetch();
                }}
                className="flex items-center gap-2 rounded-[8px] bg-[#001836] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] transition-colors"
              >
                <Send size={13} /> Submit to NCA
              </button>
            </>
          )}
        </div>
      </div>

      {submitError && (
        <div className="rounded-[8px] border border-[#E31937]/30 bg-[#ffe8e8] px-4 py-3 text-[12px] text-[#9b1c1c]">
          {submitError}
        </div>
      )}

      {correctionOpen && (
        <div className="rounded-[12px] border border-[#ffd100] bg-[#fffdf5] p-4">
          <h2 className="text-[14px] font-semibold text-[#191c1e]">Return for correction</h2>
          <p className="mt-1 text-[12px] text-[#737780]">Choose the affected section and explain exactly what Data Entry must correct.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-[220px_1fr]">
            <select value={correctionSection} onChange={(event) => setCorrectionSection(event.target.value)}
              className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px]">
              {sections.map((section) => <option key={section.section_code} value={section.section_code}>{section.title}</option>)}
            </select>
            <textarea value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} rows={2}
              className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px]" placeholder="Required correction instructions" />
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setCorrectionOpen(false)} className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[12px]">Cancel</button>
            <button type="button" disabled={!correctionReason.trim() || !correctionSection}
              onClick={async () => {
                await api.post(`/submissions/${submission?.id}/provider-review/request-correction/`, {
                  reason: correctionReason,
                  targets: [{ type: "SECTION", id: correctionSection, instruction: correctionReason }],
                });
                setCorrectionOpen(false); setCorrectionReason(""); await expectedQ.refetch();
              }}
              className="rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white disabled:opacity-50">Send correction request</button>
          </div>
        </div>
      )}

      {timelineQ.data && timelineQ.data.length > 0 && (
        <section className="rounded-[12px] border border-[#e6e8ea] bg-white p-4">
          <h2 className="text-[13px] font-semibold text-[#191c1e]">Submission timeline</h2>
          <div className="mt-3 space-y-3 border-l-2 border-[#dce3e9] pl-4">
            {timelineQ.data.map(event => <div key={event.id}>
              <p className="text-[12px] font-medium text-[#191c1e]">{event.message}</p>
              <p className="mt-0.5 text-[10px] text-[#737780]">{event.actor_name || "System"} · {new Date(event.created_at).toLocaleString()}</p>
            </div>)}
          </div>
        </section>
      )}

      {isDataEntry && ["DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"].includes(expected.workflow_status) && completion && !completion.can_submit && (
        <div className="rounded-[8px] border border-[#ffd100] bg-[#fff3bf]/50 px-4 py-3 text-[12px] text-[#7a5c00]">
          Complete {completion.missing_required_count} required item{completion.missing_required_count === 1 ? "" : "s"} before submitting.
          {completion.blocking_issues.slice(0, 3).map((issue) => (
            <span key={`${issue.type}-${issue.id}`} className="ml-2">• {issue.label}</span>
          ))}
        </div>
      )}

      {periodForms.length > 1 && (
        <div className="rounded-[12px] border border-[#e6e8ea] bg-white px-4 py-3"
          style={{ boxShadow: "0 1px 4px rgba(0,45,91,0.04)" }}>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">Period forms</p>
              <p className="text-[12px] text-[#43474f]">{expected.period_name}</p>
            </div>
            <p className="text-[11px] text-[#737780]">
              {periodForms.findIndex((item) => item.id === expected.id) + 1} of {periodForms.length}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {periodForms.map((item) => {
              const active = item.id === expected.id;
              return (
                <Link
                  key={item.id}
                  href={`/provider/submissions/${item.id}`}
                  className={`rounded-[8px] border px-3 py-2 text-[12px] transition-colors ${
                    active
                      ? "border-[#0066cc] bg-[#e8f1fb] text-[#004999]"
                      : "border-[#e6e8ea] bg-[#f7f9fb] text-[#43474f] hover:border-[#c3c6d0] hover:bg-white"
                  }`}
                >
                  <span className="font-semibold">{item.form_code}</span>
                  <span className="ml-2 text-[11px] opacity-75">{item.workflow_status.split("_").join(" ")}</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Main layout: stepper + content */}
      <div className="flex gap-5 items-start">
        {/* Section stepper */}
        <SectionStepper
          sections={completion?.sections ?? sections.map((s) => ({
            section_code: s.section_code,
            title: s.title,
            required: s.fields.filter((f) => f.is_required).length,
            provided: 0,
            complete: false,
          }))}
          activeSection={activeSection}
          onSelect={setActiveSection}
          completionPct={completion?.completion_pct ?? 0}
        />

        {/* Section content */}
        <div className="flex-1 min-w-0 rounded-[16px] border border-[#e6e8ea] bg-white p-6"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
          {currentSection && submission && (
            <SectionContent
              section={currentSection}
              submissionId={submission.id}
              isEditable={isEditable}
              kmzRequired={!!form.kmz_required}
              submissionRevision={submission.revision}
            />
          )}

          {/* Prev / Next navigation */}
          <div className="flex items-center justify-between mt-8 pt-5 border-t border-[#eceef0]">
            <button
              onClick={() => setActiveSection(sections[currentSectionIndex - 1]?.section_code)}
              disabled={currentSectionIndex === 0}
              className="flex items-center gap-1.5 rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[12px] font-medium text-[#43474f] hover:bg-[#f2f4f6] disabled:opacity-40 transition-colors"
            >
              <ChevronLeft size={13} />
              Previous
            </button>
            <p className="text-[11px] text-[#737780] tabular-nums">
              {currentSectionIndex + 1} of {sections.length}
            </p>
            <button
              onClick={() => setActiveSection(sections[currentSectionIndex + 1]?.section_code)}
              disabled={currentSectionIndex >= sections.length - 1}
              className="flex items-center gap-1.5 rounded-[8px] bg-[#002d5b] px-3 py-2 text-[12px] font-medium text-white hover:bg-[#001836] disabled:opacity-40 transition-colors"
            >
              Next
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

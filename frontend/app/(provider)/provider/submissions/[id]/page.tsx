"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { SectionStepper } from "@/components/forms/SectionStepper";
import { FieldRenderer } from "@/components/forms/FieldRenderer";
import { GridRenderer } from "@/components/forms/GridRenderer";
import { KMZUploadPanel } from "@/components/forms/KMZUploadPanel";
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
import { api } from "@/lib/api";
import { Save, Send, ChevronRight, ChevronLeft, AlertTriangle } from "lucide-react";
import type { FormSection, FieldStatus } from "@/lib/types";

// ─── Local value state for one section ───────────────────────────────────────

type FieldValues = Record<string, { value: string; status: FieldStatus | ""; explanation: string }>;

function useSectionFieldState(
  sectionFields: FormSection["fields"],
  serverValues: { field?: number | null; value: string; value_status: string; explanation: string }[] | undefined
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
}: {
  section: FormSection;
  submissionId: number;
  isEditable: boolean;
  kmzRequired: boolean;
}) {
  const serverValues = useSectionValues(submissionId, section.section_code);
  const saveMutation = useSaveSectionValues(submissionId);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<"saved" | "error" | null>(null);

  const [fieldValues, setFieldValues] = useSectionFieldState(section.fields, serverValues.data ?? []);
  const [gridValues, setGridValues] = useState<Record<number, { grid_row_id: string; grid_column_id: number; value: string; value_status: string }[]>>({});

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
        rows.map((r) => ({ grid: Number(gid), grid_row_id: r.grid_row_id, grid_column: r.grid_column_id, value: r.value, value_status: r.value_status }))
      );
      await saveMutation.mutateAsync({ sectionCode: section.section_code, values: [...fieldPayload, ...gridPayload] });
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
    await fetch(`/api/v1/submissions/${submissionId}/kmz-uploads/`, {
      method: "POST",
      body: form,
    });
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
      {kmzRequired && section.kmz_upload_required && (
        <KMZUploadPanel
          submissionId={submissionId}
          requirementId={1}
          category="Route / Topology"
          description="Upload a KMZ file showing your fibre route or network topology for this section."
          isRequired
          uploads={[]}
          onUpload={handleKMZUpload}
          disabled={!isEditable}
        />
      )}

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

      {/* Auto-save prompt when dirty */}
      {dirty && isEditable && (
        <div className="flex items-center gap-2 rounded-[8px] border border-[#ffd100] bg-[#fff3bf]/60 px-3 py-2 text-[12px] text-[#7a5c00]">
          <AlertTriangle size={12} />
          You have unsaved changes. Click "Save progress" to avoid losing data.
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

  // Get or create submission
  const latestSubmissionId = expected ? (expected as { latest_submission_id?: number }).latest_submission_id ?? null : null;
  const submissionQ = useSubmission(latestSubmissionId);
  const submission = submissionQ.data;

  const formQ = useFormTemplate(expected?.form_template ?? 0);
  const form = formQ.data;

  const completionQ = useSubmissionCompletion(submission?.id ?? null);
  const completion = completionQ.data;

  const startMutation = useStartSubmission();
  const submitMutation = useSubmitForApproval(submission?.id ?? 0);

  const sections = form?.sections ?? [];
  const [activeSection, setActiveSection] = useState<string>("");

  useEffect(() => {
    if (sections.length && !activeSection) {
      setActiveSection(sections[0].section_code);
    }
  }, [sections, activeSection]);

  const currentSectionIndex = sections.findIndex((s) => s.section_code === activeSection);
  const currentSection = sections[currentSectionIndex];

  const isEditable = expected?.workflow_status === "DRAFT" || expected?.workflow_status === "CORRECTION_REQUESTED";

  async function handleStart() {
    if (!expectedId) return;
    await startMutation.mutateAsync(expectedId);
    expectedQ.refetch();
  }

  async function handleSubmitForApproval() {
    await submitMutation.mutateAsync();
    expectedQ.refetch();
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
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center space-y-4">
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
          <button
            onClick={handleStart}
            disabled={startMutation.isPending}
            className="w-full rounded-[8px] bg-[#002d5b] px-4 py-2.5 text-[14px] font-semibold text-white hover:bg-[#001836] disabled:opacity-60 transition-colors"
          >
            {startMutation.isPending ? "Starting…" : "Start form"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
          {isDataEntry && expected.workflow_status === "DRAFT" && (
            <button
              onClick={handleSubmitForApproval}
              disabled={submitMutation.isPending || (completion?.completion_pct ?? 0) < 1}
              className="flex items-center gap-2 rounded-[8px] bg-[#1f7a4d] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#185e3b] disabled:opacity-50 transition-colors"
              title="Complete all required fields before submitting to your approver"
            >
              <Send size={13} />
              {submitMutation.isPending ? "Submitting…" : "Submit to Approver"}
            </button>
          )}
          {/* APPROVER: can return to data entry or officially submit to NCA */}
          {isApprover && expected.workflow_status === "PENDING_APPROVAL" && (
            <>
              <button
                onClick={async () => {
                  await api(`/submissions/${submission?.id}/return-to-draft/`, { method: "POST" });
                  expectedQ.refetch();
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

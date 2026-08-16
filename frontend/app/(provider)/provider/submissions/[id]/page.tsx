"use client";

import { useState, useEffect, useMemo, useRef } from "react";
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
type ProviderReviewData = {
  correction_items:Array<{id:number;stage:string;target_type:string;target_id:string;instruction:string;status:string}>;
  provider_edits:Array<{id:number;actor_name:string;section_code:string;item_count:number;created_at:string}>;
  permitted_actions:string[];
};

function formatDate(value: string | null | undefined) {
  if (!value) return "Not yet";
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function AssignmentSummary({ expected }: { expected: ExpectedSubmission }) {
  const team = (expected.data_entry_team ?? []).map((member) => member.name).join(", ") || "No active Data Entry users";
  const items = [
    ["Organisation", expected.provider_name],
    ["Reporting period", expected.period_name],
    ["Data Entry ownership", expected.ownership_label || "Shared Data Entry queue"],
    ["Active Data Entry team", team],
    ["Form version", `${expected.form_code}${expected.form_version ? ` v${expected.form_version}` : ""}`],
    ["Form created", formatDate(expected.form_created_at)],
    ["Sent to provider", formatDate(expected.sent_at || expected.created_at)],
    ["Provider submitted", formatDate(expected.submitted_at)],
  ];
  return (
    <section className="rounded-[14px] border border-[#dce3e9] bg-gradient-to-br from-white to-[#f7f9fb] p-4 shadow-[0_2px_8px_rgba(0,45,91,0.05)]">
      <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
        {items.map(([label, value]) => <div key={label} className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{label}</p>
          <p className="mt-1 break-words text-[12px] font-medium text-[#191c1e]">{value}</p>
        </div>)}
      </div>
      <div className="mt-4 border-t border-[#e6e8ea] pt-3 text-[11px] text-[#5e6269]">
        Most recent Data Entry edit: {expected.last_data_entry_editor
          ? `${expected.last_data_entry_editor.name} · ${formatDate(expected.last_data_entry_editor.edited_at)}`
          : "No Data Entry values saved yet"}
      </div>
    </section>
  );
}

function useSectionFieldState(
  sectionFields: FormSection["fields"],
  serverValues: { field?: number | null; value: string; value_status: string; explanation?: string }[] | undefined,
  allowServerSync: boolean,
) {
  const [fieldValues, setFieldValues] = useState<FieldValues>({});

  useEffect(() => {
    if (!serverValues || !allowServerSync) return;
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
  }, [serverValues, sectionFields, allowServerSync]);

  return [fieldValues, setFieldValues] as const;
}

// ─── Section Content ──────────────────────────────────────────────────────────

function SectionContent({
  section,
  submissionId,
  isEditable,
  kmzRequired,
  submissionRevision,
  validationIssues,
  correctionItems,
}: {
  section: FormSection;
  submissionId: number;
  isEditable: boolean;
  kmzRequired: boolean;
  submissionRevision: number;
  validationIssues: Array<{target_type:string;target_id:string;message:string}>;
  correctionItems: Array<{target_type:string;target_id:string;instruction:string;status:string}>;
}) {
  const serverValues = useSectionValues(submissionId, section.section_code);
  const saveMutation = useSaveSectionValues(submissionId);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<"saved" | "error" | null>(null);
  const [saveError, setSaveError] = useState("");
  const [conflict, setConflict] = useState<{current_revision:number;last_edited_by_name?:string;last_edited_at?:string} | null>(null);
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [fieldValues, setFieldValues] = useSectionFieldState(section.fields, serverValues.data ?? [], !dirty);
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
    setSaveError("");
    try {
      const fieldPayload = Object.entries(fieldValues).filter(([, v]) => Boolean(v.status || v.value || v.explanation)).map(([fid, v]) => ({
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
    } catch (error) {
      setSaveMsg("error");
      if (error instanceof ApiError) {
        setSaveError(error.message);
        const data = error.data as {code?:string;current_revision?:number;last_edited_by_name?:string;last_edited_at?:string} | undefined;
        if (data?.code === "STALE_REVISION" && data.current_revision !== undefined) setConflict({ current_revision:data.current_revision, last_edited_by_name:data.last_edited_by_name, last_edited_at:data.last_edited_at });
      } else setSaveError("Save failed. Your local values are still on this page.");
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

  useEffect(() => () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current); }, []);
  useEffect(() => {
    if (!dirty || saving || conflict || !isEditable) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => { void handleSave(); }, 1200);
    return () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current); };
    // handleSave intentionally runs against the latest field/grid render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldValues, gridValues, dirty, saving, conflict, isEditable]);

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

  const orderedFieldItems = [
    ...(section.headings??[]).map(heading=>({kind:"heading" as const,sortOrder:heading.sort_order,heading})),
    ...section.fields.map(field=>({kind:"field" as const,sortOrder:field.sort_order,field})),
  ].sort((left,right)=>left.sortOrder-right.sortOrder);

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
      {orderedFieldItems.length > 0 && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {orderedFieldItems.map((item) => {
            if (item.kind === "heading") return <div key={`heading-${item.heading.id}`} className={`md:col-span-2 ${item.heading.level===1?'border-b-2 border-[#001836] pb-2 pt-3':item.heading.level===2?'rounded-lg border-l-4 border-[#0066cc] bg-[#e8f1fb] px-4 py-3':'border-l-2 border-[#8aa9c7] pl-3'}`}><h3 className={item.heading.level===1?'text-[16px] font-semibold text-[#001836]':'text-[13px] font-semibold text-[#23364d]'}>{item.heading.title}</h3></div>;
            const field = item.field;
            const fv = fieldValues[field.id] ?? { value: "", status: "", explanation: "" };
            return (
              <div key={field.id} className={`${field.field_type === "textarea" || field.field_type === "declaration" ? "md:col-span-2" : ""} ${isEditable ? "rounded-[10px] border border-[#eceef0] bg-[#fbfcfd] p-4" : ""}`}>
                <FieldRenderer
                  field={field}
                  value={fv.value}
                  valueStatus={fv.status}
                  explanation={fv.explanation}
                  onChange={(v, s, e) => handleFieldChange(field.id, v, s, e)}
                  disabled={!isEditable}
                  readOnlyPresentation={!isEditable}
                  allFieldValues={Object.fromEntries(
                    Object.entries(fieldValues).map(([k, v]) => [k, { value: v.value }])
                  )}
                  issues={validationIssues.filter((issue) => issue.target_type === "FIELD" && String(issue.target_id) === String(field.id)).map((issue) => issue.message)}
                  correctionInstructions={correctionItems.filter((item) => item.status === "OPEN" && item.target_type === "FIELD" && String(item.target_id) === String(field.id)).map((item) => item.instruction)}
                  onBlur={() => { if (dirty && !saving && !conflict) void handleSave(); }}
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
            readOnlyPresentation={!isEditable}
            issues={validationIssues.filter((issue) => issue.target_type === "GRID_CELL").map((issue) => ({ targetId:String(issue.target_id), message:issue.message }))}
            correctionInstructions={correctionItems.filter((item) => item.status === "OPEN" && item.target_type === "GRID_CELL").map((item) => ({ targetId:String(item.target_id), instruction:item.instruction }))}
          />
        </div>
      ))}

      {/* Excel backup panel — available for all forms */}
      <div className={isEditable ? "" : "opacity-90"}>
        <ExcelBackupPanel
          submissionId={submissionId}
          uploads={excelUploads}
          onUpload={handleExcelUpload}
          disabled={!isEditable}
          description="Upload an Excel file as a backup. This is stored for source control only and not analyzed."
        />
      </div>

      {/* Auto-save prompt when dirty */}
      {dirty && isEditable && (
        <div className="flex items-center gap-2 rounded-[8px] border border-[#ffd100] bg-[#fff3bf]/60 px-3 py-2 text-[12px] text-[#7a5c00]">
          <AlertTriangle size={12} />
          Changes are waiting to autosave. You can also use Save progress.
        </div>
      )}
      {saveError && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{saveError}</div>}
      {conflict && <div role="alert" className="rounded-lg border border-[#ffd100] bg-[#fff3bf] p-3 text-xs text-[#7a5c00]">
        A newer revision was saved by {conflict.last_edited_by_name || "another provider user"}{conflict.last_edited_at ? ` at ${new Date(conflict.last_edited_at).toLocaleString()}` : ""}. Your unsaved values remain visible. Reload the latest revision before manually reapplying them.
        <button onClick={() => window.location.reload()} className="ml-3 font-semibold underline">Reload latest</button>
      </div>}
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
  const providerReviewQ = useQuery<ProviderReviewData>({
    queryKey: ["provider-review-data", latestSubmissionId],
    queryFn: () => api(`/submissions/${latestSubmissionId}/provider-review-data/`),
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
  const [correctionTargets, setCorrectionTargets] = useState<string[]>([]);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [attestation, setAttestation] = useState(false);
  const [approvalNote, setApprovalNote] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [actionError, setActionError] = useState("");
  const [receiptReference, setReceiptReference] = useState<string | null>(null);

  async function handleStart() {
    if (!expectedId) return;
    await startMutation.mutateAsync(expectedId);
    expectedQ.refetch();
  }

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

  const isEditable = Boolean(providerReviewQ.data?.permitted_actions.includes("EDIT"));
  const correctionOptions = useMemo(() => sections.flatMap((section) => [
    { key:`SECTION:${section.section_code}`, label:`Section: ${section.title}` },
    ...section.fields.map((field) => ({ key:`FIELD:${field.id}`, label:`${section.title} · ${field.label}` })),
    ...section.grids.map((grid) => ({ key:`SECTION:${section.section_code}`, label:`${section.title} · ${grid.title} (whole grid)` })),
  ]).filter((option, index, all) => all.findIndex((candidate) => candidate.key === option.key) === index), [sections]);

  async function handleSubmitForApproval() {
    setSubmitError(null);
    try {
      await submitMutation.mutateAsync();
      await Promise.all([
        expectedQ.refetch(), providerReviewQ.refetch(), completionQ.refetch(), periodFormsQ.refetch(),
      ]);
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
  if (expected.workflow_status === "NOT_STARTED" && !isDataEntry && !isApprover) {
    return (
      <div className="space-y-4">
        <Link href="/provider/dashboard"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
          <ChevronLeft size={14} /> Back to My Forms
        </Link>
        <AssignmentSummary expected={expected} />
        <div className="flex flex-col items-center justify-center min-h-[300px] text-center">
        <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-8 max-w-lg space-y-4"
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
              Read-only monitoring is available now. A Provider Data Entry user must start the form before values can be entered; it becomes editable for you only after submission to the Approver queue.
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
          {isDataEntry && ["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"].includes(expected.workflow_status) && (
            <button
              onClick={handleSubmitForApproval}
              disabled={submitMutation.isPending || !completion?.transition_ready}
              className="flex items-center gap-2 rounded-[8px] bg-[#1f7a4d] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#185e3b] disabled:opacity-50 transition-colors"
              title="Blank indicators are allowed; only genuine blockers prevent submission"
            >
              <Send size={13} />
              {submitMutation.isPending ? "Submitting…" : "Submit to Approver"}
            </button>
          )}
          {/* APPROVER: can return to data entry or officially submit to NCA */}
          {isApprover && ["PENDING_APPROVAL", "PROVIDER_RESUBMITTED", "CORRECTION_REQUESTED"].includes(expected.workflow_status) && (
            <>
              <button
                onClick={() => {
                  setCorrectionTargets([`SECTION:${activeSection || sections[0]?.section_code || ""}`]);
                  setCorrectionOpen(true);
                }}
                className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] px-4 py-2.5 text-[13px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors"
              >
                Return to Data Entry
              </button>
              <button
                onClick={() => setApprovalOpen(true)}
                className="flex items-center gap-2 rounded-[8px] bg-[#001836] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] transition-colors"
              >
                <Send size={13} /> Submit to NCA
              </button>
            </>
          )}
        </div>
      </div>

      <AssignmentSummary expected={expected} />

      {isApprover && !isEditable && ["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"].includes(expected.workflow_status) && (
        <div className="rounded-[10px] border border-[#b9d4ef] bg-[#eef6ff] px-4 py-3 text-[12px] text-[#264f73]">
          Read-only monitoring view. You can see saved values and progress now; editing becomes available after Data Entry submits this form to the Approver queue.
        </div>
      )}
      {isApprover && !isEditable && !["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"].includes(expected.workflow_status) && (
        <div className="rounded-[10px] border border-[#dce3e9] bg-[#f7f9fb] px-4 py-3 text-[12px] text-[#5e6269]">
          This official provider version is read-only. Its submitted values, receipt and review progress remain available here.
        </div>
      )}
      {isDataEntry && !isEditable && (
        <div className="rounded-[10px] border border-[#b9d4ef] bg-[#eef6ff] px-4 py-3 text-[12px] text-[#264f73]">
          This form is read-only while it is with the Provider Approver or NCA. Saved values and review progress remain visible here.
        </div>
      )}

      {submitError && (
        <div className="rounded-[8px] border border-[#E31937]/30 bg-[#ffe8e8] px-4 py-3 text-[12px] text-[#9b1c1c]">
          {submitError}
        </div>
      )}

      {correctionOpen && (
        <div className="rounded-[12px] border border-[#ffd100] bg-[#fffdf5] p-4">
          <h2 className="text-[14px] font-semibold text-[#191c1e]">Return for correction</h2>
          <p className="mt-1 text-[12px] text-[#737780]">Select one or more exact sections or fields and provide instructions. Data Entry can edit only those targets.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr]">
            <div className="max-h-48 overflow-y-auto rounded-lg border bg-white p-2">{correctionOptions.map((option) => <label key={option.key} className="flex items-start gap-2 px-2 py-1.5 text-xs"><input type="checkbox" checked={correctionTargets.includes(option.key)} onChange={(e) => setCorrectionTargets((current) => e.target.checked ? [...current, option.key] : current.filter((key) => key !== option.key))} /><span>{option.label}</span></label>)}</div>
            <textarea value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} rows={2}
              className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px]" placeholder="Required correction instructions" />
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setCorrectionOpen(false)} className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[12px]">Cancel</button>
            <button type="button" disabled={!correctionReason.trim() || correctionTargets.length === 0}
              onClick={async () => {
                await api.post(`/submissions/${submission?.id}/provider-review/request-correction/`, {
                  reason: correctionReason,
                  targets: correctionTargets.map((target) => { const [type, id] = target.split(":", 2); return { type, id, instruction: correctionReason }; }),
                });
                setCorrectionOpen(false); setCorrectionReason(""); await expectedQ.refetch();
              }}
              className="rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white disabled:opacity-50">Send correction request</button>
          </div>
        </div>
      )}

      {approvalOpen && <div className="rounded-xl border border-[#0066cc] bg-[#f7fbff] p-5">
        <h2 className="font-semibold">Final provider approval</h2><p className="mt-1 text-xs text-[#43474f]">A fresh readiness check is performed before NCA receives the official version.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2"><div className="rounded-lg bg-white p-3 text-xs"><strong>Readiness</strong><p className="mt-1">{completion?.blocking_issues.length ?? 0} blockers · {completion?.missing_indicator_count ?? 0} blank indicators · {completion?.open_correction_item_count ?? 0} open corrections</p></div><div className="rounded-lg bg-white p-3 text-xs"><strong>Approver edits</strong><p className="mt-1">{providerReviewQ.data?.provider_edits.length ?? 0} edit batches are recorded for this version.</p></div></div>
        <label className="mt-4 block text-xs font-medium">Approval note (optional)<textarea value={approvalNote} onChange={(e) => setApprovalNote(e.target.value)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2" rows={2} /></label>
        {(providerReviewQ.data?.provider_edits.length ?? 0) > 0 && <label className="mt-3 block text-xs font-medium">Required change summary<textarea value={changeSummary} onChange={(e) => setChangeSummary(e.target.value)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2" rows={3} placeholder="Summarize what you changed and why." /></label>}
        <label className="mt-4 flex items-start gap-2 text-sm"><input type="checkbox" checked={attestation} onChange={(e) => setAttestation(e.target.checked)} className="mt-1" /><span>I attest that I reviewed this return and that the information supplied is accurate to the best of my knowledge. Any blank indicators will remain visible to NCA.</span></label>
        {actionError && <p role="alert" className="mt-3 text-xs text-red-700">{actionError}</p>}
        <div className="mt-4 flex justify-end gap-2"><button onClick={() => setApprovalOpen(false)} className="rounded-lg border px-4 py-2 text-xs">Cancel</button><button disabled={!attestation || ((providerReviewQ.data?.provider_edits.length ?? 0) > 0 && !changeSummary.trim()) || !completion?.transition_ready} onClick={async () => { try { setActionError(""); const response = await api.post<{receipt_reference:string}>(`/submissions/${submission?.id}/provider-review/approve/`, { attestation, approval_note:approvalNote, change_summary:changeSummary }); setReceiptReference(response.receipt_reference); setApprovalOpen(false); await Promise.all([expectedQ.refetch(), providerReviewQ.refetch(), completionQ.refetch(), periodFormsQ.refetch(), timelineQ.refetch(), submissionQ.refetch()]); } catch (error) { setActionError(error instanceof ApiError ? error.message : "Official submission failed."); } }} className="rounded-lg bg-[#001836] px-5 py-2 text-xs font-semibold text-white disabled:opacity-50">Submit officially to NCA</button></div>
      </div>}

      {(receiptReference || submission?.receipt_reference) && <div className="flex items-center justify-between rounded-xl border border-green-200 bg-green-50 p-4 text-sm"><span>Official receipt: <strong>{receiptReference || submission?.receipt_reference}</strong></span><button onClick={() => import("@/lib/api").then(({downloadAuthenticated}) => downloadAuthenticated(`/submissions/${submission?.id}/receipt/`, {}, `submission-receipt-${submission?.id}.pdf`))} className="font-semibold text-[#0066cc]">Download receipt</button></div>}

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

      {completion && completion.missing_indicator_count > 0 && (
        <div className="rounded-[8px] border border-[#b9d4ef] bg-[#eef6ff] px-4 py-3 text-[12px] text-[#264f73]">
          {["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "REJECTED", "ARCHIVED"].includes(expected.workflow_status)
            ? `${completion.missing_indicator_count} requested indicator${completion.missing_indicator_count === 1 ? " was" : "s were"} submitted blank and remain visible to reviewers.`
            : `${completion.missing_indicator_count} requested indicator${completion.missing_indicator_count === 1 ? " is" : "s are"} blank. You may continue and submit; reviewers will see these blanks.`}
        </div>
      )}

      {isEditable && completion && !completion.transition_ready && (
        <div className="rounded-[8px] border border-[#e6a5ae] bg-[#fff1f2] px-4 py-3 text-[12px] text-[#8f1d2c]">
          Resolve {completion.blocking_issues.length} blocking issue{completion.blocking_issues.length === 1 ? "" : "s"} before submitting.
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
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* Section stepper */}
        <div className="hidden lg:block"><SectionStepper
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
        /></div>

        <label className="block lg:hidden">
          <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">Form section</span>
          <select value={activeSection} onChange={(event) => setActiveSection(event.target.value)} className="w-full rounded-[9px] border border-[#c3c6d0] bg-white px-3 py-2.5 text-[13px] text-[#191c1e]">
            {sections.map((section, index) => <option key={section.section_code} value={section.section_code}>{index + 1}. {section.title}</option>)}
          </select>
        </label>

        {/* Section content */}
        <div className="w-full min-w-0 flex-1 rounded-[16px] border border-[#e6e8ea] bg-white p-4 sm:p-6"
          style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
          {currentSection && submission && (
            <SectionContent
              section={currentSection}
              submissionId={submission.id}
              isEditable={isEditable}
              kmzRequired={!!form.kmz_required}
              submissionRevision={submission.revision}
              validationIssues={completion?.validation_issues ?? []}
              correctionItems={providerReviewQ.data?.correction_items ?? []}
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

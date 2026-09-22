"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { SectionStepper } from "@/components/forms/SectionStepper";
import { FieldRenderer } from "@/components/forms/FieldRenderer";
import { GridRenderer } from "@/components/forms/GridRenderer";
import { KMZUploadPanel } from "@/components/forms/KMZUploadPanel";
import { ExcelBackupPanel } from "@/components/forms/ExcelBackupPanel";
import { EmailHandoffModal } from "@/components/communications/EmailHandoffModal";
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
import { Save, Send, ChevronRight, ChevronLeft, AlertTriangle, FileSpreadsheet, RefreshCw } from "lucide-react";
import type { ExpectedSubmission, FormSection, FormTemplate, FieldStatus, SubmissionCommunication, SubmissionComplianceFlag } from "@/lib/types";

// ─── Local value state for one section ───────────────────────────────────────

type FieldValues = Record<string, { value: string; status: FieldStatus | ""; explanation: string; value_source?:string }>;
type GridCellValue = { grid_row_id: string; grid_column_id: number; value: string; value_status: FieldStatus | ""; explanation?: string; value_source?:string };
type TimelineEvent = { id:number; event_type:string; message:string; from_status:string; to_status:string; actor_name:string|null; created_at:string };
type ProviderReviewData = {
  template?: FormTemplate & { sections: FormSection[] };
  correction_items:Array<{id:number;stage:string;target_type:string;target_id:string;instruction:string;status:string}>;
  compliance_flags:SubmissionComplianceFlag[];
  provider_edits:Array<{id:number;actor_name:string;section_code:string;item_count:number;created_at:string}>;
  permitted_actions:string[];
  previous_month?: { period:{id?:number;name?:string;year:number;month:number;submission_id?:number}|null; values:Record<string,string|null> };
};
type MonthlyReport = { id?:number; status:string; filename?:string; file_size?:number; sha256?:string; error_message?:string; detail?:string; download_ready:boolean };

function formatDate(value: string | null | undefined) {
  if (!value) return "Not yet";
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function AssignmentSummary({ expected }: { expected: ExpectedSubmission }) {
  const team = (expected.data_entry_team ?? []).map((member) => member.name).join(", ") || "No active Data Entry users";
  const items = [
    ["Form reference", expected.form_reference],
    ["Submission ID", expected.provider_status === "CLOSED" ? (expected.submission_reference || "Pending") : "Created after Provider Approver submission"],
    ["Organisation", expected.provider_name],
    ["Reporting period", expected.period_name],
    ["Data Entry ownership", expected.ownership_label || "Shared Data Entry queue"],
    ["Active Data Entry team", team],
    ["Form version", `${expected.form_code}${expected.form_version ? ` v${expected.form_version}` : ""}`],
    ["Form created", formatDate(expected.form_created_at)],
    ["Sent to provider", formatDate(expected.sent_at || expected.created_at)],
    ["Provider submitted", formatDate(expected.submitted_at)],
    ["Penalty amount", `GH₵${Number(expected.penalty_amount_ghs || 0).toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`],
    ["Penalty reference", expected.penalty_reference || "No penalty assigned"],
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
  serverValues: { field?: number | null; value: string; value_status: string; explanation?: string; value_source?:string }[] | undefined,
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
        value_source: sv?.value_source,
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
  registerSaveController,
  previousValues,
  onSaved,
}: {
  section: FormSection;
  submissionId: number;
  isEditable: boolean;
  kmzRequired: boolean;
  submissionRevision: number;
  validationIssues: Array<{target_type:string;target_id:string;message:string}>;
  correctionItems: Array<{target_type:string;target_id:string;instruction:string;status:string}>;
  registerSaveController: (controller: { flush:()=>Promise<boolean>; hasUnsaved:()=>boolean } | null) => void;
  previousValues: Record<string, string | null>;
  onSaved: () => void;
}) {
  const serverValues = useSectionValues(submissionId, section.section_code);
  const saveMutation = useSaveSectionValues(submissionId);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<"saved" | "error" | null>(null);
  const [saveError, setSaveError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [conflict, setConflict] = useState<{current_revision:number;last_edited_by_name?:string;last_edited_at?:string} | null>(null);
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dirtyRef = useRef(false);
  const savingRef = useRef(false);
  const fieldValuesRef = useRef<FieldValues>({});
  const gridValuesRef = useRef<Record<number, GridCellValue[]>>({});
  const revisionRef = useRef(submissionRevision);
  const localChangeVersion = useRef(0);
  const inFlightSave = useRef<Promise<boolean> | null>(null);
  const saveRunnerRef = useRef<() => Promise<boolean>>(async () => false);

  const [fieldValues, setFieldValues] = useSectionFieldState(section.fields, serverValues.data, !dirty && !saving);
  const [gridValues, setGridValues] = useState<Record<number, GridCellValue[]>>({});
  const [kmzUploads, setKmzUploads] = useState<any[]>([]);
  const queryClient = useQueryClient();

  useEffect(() => { fieldValuesRef.current = fieldValues; }, [fieldValues]);
  useEffect(() => { gridValuesRef.current = gridValues; }, [gridValues]);
  useEffect(() => { dirtyRef.current = dirty; }, [dirty]);
  useEffect(() => { savingRef.current = saving; }, [saving]);
  useEffect(() => { if (!dirtyRef.current && !savingRef.current) revisionRef.current = submissionRevision; }, [submissionRevision]);

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
        value_source: value.value_source,
      });
    }
    if (!dirtyRef.current && !savingRef.current) setGridValues(grouped);
  }, [serverValues.data]);

  useEffect(() => {
    if (!kmzRequired) return;
    api.get<any[]>(`/submissions/${submissionId}/kmz-uploads/`)
      .then(setKmzUploads)
      .catch((err) => setUploadError(err instanceof ApiError ? err.message : "KMZ files could not be loaded."));
  }, [kmzRequired, submissionId]);

  function handleFieldChange(fieldId: number, value: string, status: FieldStatus | "", explanation: string) {
    setFieldValues((prev) => ({ ...prev, [fieldId]: { value, status, explanation, value_source:"MANUAL" } }));
    localChangeVersion.current += 1;
    dirtyRef.current = true;
    setDirty(true);
  }

  const handleSave = useCallback(async (): Promise<boolean> => {
    if (!isEditable || conflict) return !dirtyRef.current;
    if (inFlightSave.current) {
      const succeeded = await inFlightSave.current;
      if (!succeeded) return false;
      return dirtyRef.current ? saveRunnerRef.current() : true;
    }
    if (!dirtyRef.current) return true;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    const savedChangeVersion = localChangeVersion.current;
    const savedFields = fieldValuesRef.current;
    const savedGrids = gridValuesRef.current;
    const clientSaveId = crypto.randomUUID();
    setSaving(true);
    savingRef.current = true;
    setSaveMsg(null);
    setSaveError("");
    const operation = (async () => {
      try {
      const fieldPayload = Object.entries(savedFields).filter(([, v]) => Boolean(v.status || v.value || v.explanation)).map(([fid, v]) => ({
        field: Number(fid),
        value: v.value,
        value_status: v.status || (v.value ? "PROVIDED" : "MISSING"),
        explanation: v.explanation,
      }));
      const gridPayload = Object.entries(savedGrids).flatMap(([gid, rows]) =>
        rows.map((r) => ({ grid: Number(gid), grid_row_id: r.grid_row_id, grid_column: r.grid_column_id, value: r.value, value_status: r.value_status, explanation: r.explanation ?? "" }))
      );
      const response = await saveMutation.mutateAsync({ sectionCode: section.section_code, values: [...fieldPayload, ...gridPayload], revision: revisionRef.current, clientSaveId, changeVersion:savedChangeVersion });
      revisionRef.current = response.resulting_revision;
      onSaved();
      if (localChangeVersion.current === savedChangeVersion) {
        dirtyRef.current = false;
        setDirty(false);
        setSaveMsg("saved");
        setTimeout(() => setSaveMsg(null), 2000);
      }
      return true;
    } catch (error) {
      setSaveMsg("error");
      if (error instanceof ApiError) {
        setSaveError(error.message);
        const data = error.data as {code?:string;current_revision?:number;last_edited_by_name?:string;last_edited_at?:string} | undefined;
        if (data?.code === "STALE_REVISION" && data.current_revision !== undefined) setConflict({ current_revision:data.current_revision, last_edited_by_name:data.last_edited_by_name, last_edited_at:data.last_edited_at });
      } else setSaveError("Save failed. Your local values are still on this page.");
      return false;
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
    })();
    inFlightSave.current = operation;
    const succeeded = await operation;
    inFlightSave.current = null;
    if (succeeded && dirtyRef.current && localChangeVersion.current > savedChangeVersion) return saveRunnerRef.current();
    return succeeded && !dirtyRef.current;
  }, [conflict, isEditable, onSaved, saveMutation, section.section_code]);

  useEffect(() => { saveRunnerRef.current = handleSave; }, [handleSave]);

  async function handleKMZUpload(file: File, requirementId: number) {
    setUploadError("");
    const form = new FormData();
    form.append("file", file);
    form.append("requirement_id", String(requirementId));
    await api.upload(`/submissions/${submissionId}/kmz-uploads/`, form);
    setKmzUploads(await api.get<any[]>(`/submissions/${submissionId}/kmz-uploads/`));
    queryClient.invalidateQueries({ queryKey: ["submission-completion", submissionId] });
  }

  useEffect(() => () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current); }, []);
  useEffect(() => {
    if (!dirty || conflict || !isEditable) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => { void handleSave(); }, 1200);
    return () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current); };
  }, [fieldValues, gridValues, dirty, conflict, isEditable, handleSave]);

  useEffect(() => {
    registerSaveController({ flush:handleSave, hasUnsaved:()=>dirtyRef.current || savingRef.current });
    return () => registerSaveController(null);
  }, [handleSave, registerSaveController]);

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
                  previousValue={previousValues[`field:${section.section_code}:${field.field_code}`.toLowerCase()]}
                  submissionId={submissionId}
                  importedFromExcel={fv.value_source==="EXCEL_IMPORT"}
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
              localChangeVersion.current += 1;
              dirtyRef.current = true;
              setDirty(true);
            }}
            disabled={!isEditable}
            readOnlyPresentation={!isEditable}
            issues={validationIssues.filter((issue) => issue.target_type === "GRID_CELL").map((issue) => ({ targetId:String(issue.target_id), message:issue.message }))}
            correctionInstructions={correctionItems.filter((item) => item.status === "OPEN" && item.target_type === "GRID_CELL").map((item) => ({ targetId:String(item.target_id), instruction:item.instruction }))}
            sectionCode={section.section_code}
            previousValues={previousValues}
          />
        </div>
      ))}

      {correctionItems.filter((item) => item.status === "OPEN" && item.target_type === "SECTION" && item.target_id === section.section_code).map((item, index) => (
        <div key={`${item.target_id}-${index}`} className="rounded-[9px] border border-[#ffd100] bg-[#fff8d8] px-4 py-3 text-[12px] text-[#6c5100]">
          <span className="font-semibold">Section flag:</span> {item.instruction}
        </div>
      ))}

      {/* Auto-save prompt when dirty */}
      {dirty && isEditable && (
        <div className="flex items-center gap-2 rounded-[8px] border border-[#ffd100] bg-[#fff3bf]/60 px-3 py-2 text-[12px] text-[#7a5c00]">
          <AlertTriangle size={12} />
          Changes are waiting to autosave. You can also use Save progress.
        </div>
      )}
      {saveError && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{saveError}<button type="button" onClick={() => void handleSave()} className="ml-3 font-semibold underline">Retry</button></div>}
      {uploadError && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{uploadError}<button type="button" onClick={() => window.location.reload()} className="ml-3 font-semibold underline">Retry loading</button></div>}
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const workflowQueryClient = useQueryClient();
  const expectedId = Number(params.id);
  const saveControllerRef = useRef<{flush:()=>Promise<boolean>;hasUnsaved:()=>boolean} | null>(null);
  const registerSaveController = useCallback((controller:{flush:()=>Promise<boolean>;hasUnsaved:()=>boolean} | null) => {
    saveControllerRef.current = controller;
  }, []);

  useEffect(() => {
    const warnBeforeUnload = (event:BeforeUnloadEvent) => {
      if (!saveControllerRef.current?.hasUnsaved()) return;
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, []);

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
  const actualLatestSubmissionId = expected ? (expected as { latest_submission_id?: number }).latest_submission_id ?? null : null;
  const requestedVersionId = Number(searchParams.get("version"));
  const latestSubmissionId = Number.isInteger(requestedVersionId) && requestedVersionId > 0 ? requestedVersionId : actualLatestSubmissionId;
  const isHistoricalVersion = Boolean(latestSubmissionId && actualLatestSubmissionId && latestSubmissionId !== actualLatestSubmissionId);
  const submissionQ = useSubmission(latestSubmissionId);
  const submission = submissionQ.data;
  const timelineQ = useQuery<TimelineEvent[]>({
    queryKey: ["submission-timeline", latestSubmissionId],
    queryFn: () => api(`/submissions/${latestSubmissionId}/timeline/`),
    enabled: Boolean(latestSubmissionId),
  });
  const communicationsQ = useQuery<SubmissionCommunication[]>({
    queryKey:["submission-communications",latestSubmissionId],
    queryFn:()=>api(`/submissions/${latestSubmissionId}/communications/`),
    enabled:Boolean(latestSubmissionId),
    select:(items)=>items.map((item)=>item.sender===currentUser?.id ? item : {...item,email_handoff:null}),
  });
  const providerReviewQ = useQuery<ProviderReviewData>({
    queryKey: ["provider-review-data", latestSubmissionId],
    queryFn: () => api(`/submissions/${latestSubmissionId}/provider-review-data/`),
    enabled: Boolean(latestSubmissionId),
  });
  const monthlyReportQ = useQuery<MonthlyReport>({
    queryKey: ["monthly-report", latestSubmissionId],
    queryFn: () => api(`/submissions/${latestSubmissionId}/monthly-report/`),
    enabled: Boolean(latestSubmissionId),
    refetchInterval: (query) => query.state.data?.status === "PREPARING" ? 2500 : false,
  });

  const formQ = useFormTemplate(expected?.form_template ?? 0);
  const form = providerReviewQ.data?.template ?? formQ.data;

  const completionQ = useSubmissionCompletion(submission?.id ?? null);
  const completion = completionQ.data;
  const handleSectionSaved = useCallback(() => {
    void Promise.all([
      providerReviewQ.refetch(),
      completionQ.refetch(),
      submissionQ.refetch(),
    ]);
  }, [completionQ, providerReviewQ, submissionQ]);

  const startMutation = useStartSubmission();
  const submitMutation = useSubmitForApproval(submission?.id ?? 0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionTargets, setCorrectionTargets] = useState<string[]>([]);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [officialConfirmOpen, setOfficialConfirmOpen] = useState(false);
  const [officialSubmitting, setOfficialSubmitting] = useState(false);
  const [attestation, setAttestation] = useState(false);
  const [approvalNote, setApprovalNote] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [actionError, setActionError] = useState("");
  const [receiptReference, setReceiptReference] = useState<string | null>(null);
  const [correspondenceText, setCorrespondenceText] = useState("");
  const [handoffEventId, setHandoffEventId] = useState<number|null>(null);

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

  const isEditable = !isHistoricalVersion && Boolean(providerReviewQ.data?.permitted_actions.includes("EDIT"));
  const correctionOptions = useMemo(() => sections.flatMap((section) => [
    { key:`SECTION:${section.section_code}`, label:`Section: ${section.title}` },
    ...section.fields.map((field) => ({ key:`FIELD:${field.id}`, label:`${section.title} · ${field.label}` })),
    ...section.grids.flatMap((grid) => [
      { key:`SECTION:${section.section_code}`, label:`${section.title} · ${grid.title} (whole grid)` },
      ...(grid.fixed_rows ?? []).flatMap((row) => grid.columns.map((column) => ({
        key:`GRID_CELL:${grid.id}:${row.id}:${column.id}`,
        label:`${section.title} · ${grid.title} · ${row.row_label} · ${column.label}`,
      }))),
    ]),
  ]).filter((option, index, all) => all.findIndex((candidate) => candidate.key === option.key) === index), [sections]);

  async function handleSubmitForApproval() {
    setSubmitError(null);
    try {
      if (saveControllerRef.current && !(await saveControllerRef.current.flush())) {
        setSubmitError("Your latest changes could not be saved. Retry the save before submitting.");
        return;
      }
      const response = await submitMutation.mutateAsync();
      if (response.event_id) setHandoffEventId(response.event_id);
      await refreshProviderWorkflow();
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : "Submission failed. Please try again.");
      completionQ.refetch();
    }
  }

  async function handleOfficialSubmit() {
    if (!submission?.id) return;
    setActionError("");
    setOfficialSubmitting(true);
    try {
      const response=await api.post<{receipt_reference:string;event_id:number}>(
        `/submissions/${submission.id}/provider-review/approve/`,
        {attestation,approval_note:approvalNote,change_summary:changeSummary},
      );
      setReceiptReference(response.receipt_reference);
      setOfficialConfirmOpen(false);
      setApprovalOpen(false);
      setHandoffEventId(response.event_id);
      await refreshProviderWorkflow();
    } catch (error) {
      setOfficialConfirmOpen(false);
      setActionError(error instanceof Error?error.message:"Official submission failed.");
    } finally {
      setOfficialSubmitting(false);
    }
  }

  async function navigateToSection(sectionCode:string | undefined) {
    if (!sectionCode || sectionCode === activeSection) return;
    if (saveControllerRef.current && !(await saveControllerRef.current.flush())) return;
    setActiveSection(sectionCode);
  }

  async function leaveForm(href:string) {
    if (saveControllerRef.current && !(await saveControllerRef.current.flush())) return;
    router.push(href);
  }

  async function refreshProviderWorkflow() {
    await Promise.all([
      expectedQ.refetch(), providerReviewQ.refetch(), completionQ.refetch(),
      periodFormsQ.refetch(), timelineQ.refetch(), submissionQ.refetch(),
      communicationsQ.refetch(),
      workflowQueryClient.invalidateQueries({queryKey:["provider-workspace"]}),
      workflowQueryClient.invalidateQueries({queryKey:["provider-workspace-summary"]}),
      workflowQueryClient.invalidateQueries({queryKey:["provider-approval-queue"]}),
      workflowQueryClient.invalidateQueries({queryKey:["submission-notifications"]}),
      workflowQueryClient.invalidateQueries({queryKey:["submission-notification-summary"]}),
      monthlyReportQ.refetch(),
    ]);
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
          <ChevronLeft size={14} /> Back to Dashboard
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
      <button type="button" onClick={() => void leaveForm("/provider/dashboard")}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#737780] hover:text-[#0066cc] transition-colors">
        <ChevronLeft size={14} /> Back to Dashboard
      </button>

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
          {completion && (isDataEntry || isApprover) && (
            <div className="self-center rounded-lg border border-[#dce3e9] bg-white px-3 py-2 text-right text-[11px] text-[#5e6269]" aria-live="polite">
              <span className="font-semibold text-[#191c1e]">{completion.missing_indicator_count}</span>{" "}
              blank indicator{completion.missing_indicator_count === 1 ? "" : "s"}
              {completion.blocking_issues.length > 0 && <span className="ml-2 font-semibold text-red-700">· {completion.blocking_issues.length} error{completion.blocking_issues.length === 1 ? "" : "s"}</span>}
            </div>
          )}
          {/* DATA ENTRY: can submit draft to approver */}
          {isDataEntry && ["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"].includes(expected.workflow_status) && (
            <button
              onClick={handleSubmitForApproval}
              disabled={submitMutation.isPending || !completion?.transition_ready}
              className="flex items-center gap-2 rounded-[8px] bg-[#1f7a4d] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#185e3b] disabled:opacity-50 transition-colors"
              title="Blank indicators are allowed; only genuine errors prevent submission"
            >
              <Send size={13} />
              {submitMutation.isPending ? "Submitting…" : expected.workflow_status === "PROVIDER_CHANGES_REQUESTED" ? "Resubmit to Approver" : "Submit to Approver"}
            </button>
          )}
          {/* APPROVER: can return to data entry or officially submit to NCA */}
          {isApprover && ["PENDING_APPROVAL", "PROVIDER_RESUBMITTED", "CORRECTION_REQUESTED"].includes(expected.workflow_status) && (
            <>
              <button
                onClick={() => {
                  const sectionCode = activeSection || sections[0]?.section_code || "";
                  setActionError("");
                  setCorrectionReason("");
                  setCorrectionTargets(sectionCode ? [`SECTION:${sectionCode}`] : []);
                  setCorrectionOpen(true);
                }}
                className="flex items-center gap-2 rounded-[8px] border border-[#c3c6d0] px-4 py-2.5 text-[13px] font-medium text-[#43474f] hover:bg-[#f2f4f6] transition-colors"
              >
                Return to Data Entry
              </button>
              <button
                onClick={() => { setActionError(""); setApprovalOpen(true); }}
                className="flex items-center gap-2 rounded-[8px] bg-[#001836] px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] transition-colors"
              >
                <Send size={13} /> Submit to NCA
              </button>
            </>
          )}
        </div>
      </div>

      <AssignmentSummary expected={expected} />

      {submission && <ExcelBackupPanel submissionId={submission.id} sections={sections} disabled={!isEditable} />}

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
          <h2 className="text-[14px] font-semibold text-[#191c1e]">Flag and return</h2>
          <p className="mt-1 text-[12px] text-[#737780]">Select one or more exact sections or fields and provide instructions. Data Entry can edit only those targets.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr]">
            <div className="max-h-48 overflow-y-auto rounded-lg border bg-white p-2">{correctionOptions.map((option) => <label key={option.key} className="flex items-start gap-2 px-2 py-1.5 text-xs"><input type="checkbox" checked={correctionTargets.includes(option.key)} onChange={(e) => setCorrectionTargets((current) => e.target.checked ? [...current, option.key] : current.filter((key) => key !== option.key))} /><span>{option.label}</span></label>)}</div>
            <textarea value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} rows={2}
              className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px]" placeholder="Required flag instructions" />
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setCorrectionOpen(false)} className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[12px]">Cancel</button>
            <button type="button" disabled={!correctionReason.trim() || correctionTargets.length === 0 || !submission?.id}
              onClick={async () => {
                if (!submission?.id) return;
                const targets = correctionTargets.map((target) => { const separator=target.indexOf(":"); return {type:target.slice(0,separator),id:target.slice(separator+1),instruction:correctionReason.trim()}; });
                try {
                  const response=await api.post<{event_id:number}>(`/submissions/${submission.id}/provider-review/request-correction/`,{reason:correctionReason.trim(),targets});
                  setCorrectionOpen(false);setCorrectionReason("");setCorrectionTargets([]);setHandoffEventId(response.event_id);await refreshProviderWorkflow();
                } catch (error) { setActionError(error instanceof Error?error.message:"The flagged return could not be completed."); }
              }}
              className="rounded-[8px] bg-[#002d5b] px-4 py-2 text-[12px] font-semibold text-white disabled:opacity-50">Send flagged return</button>
          </div>
          {actionError && <p role="alert" className="mt-3 text-xs text-red-700">{actionError}</p>}
        </div>
      )}

      {approvalOpen && <div className="rounded-xl border border-[#0066cc] bg-[#f7fbff] p-5">
        <h2 className="font-semibold">Final provider approval</h2><p className="mt-1 text-xs text-[#43474f]">A fresh readiness check is performed before NCA receives the official version.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2"><div className="rounded-lg bg-white p-3 text-xs"><strong>Readiness</strong><p className="mt-1">{completion?.blocking_issues.length ?? 0} errors · {completion?.missing_indicator_count ?? 0} blank indicators · {completion?.open_correction_item_count ?? 0} open flags</p></div><div className="rounded-lg bg-white p-3 text-xs"><strong>Approver edits</strong><p className="mt-1">{providerReviewQ.data?.provider_edits.length ?? 0} edit batches are recorded for this version.</p></div></div>
        {(providerReviewQ.data?.provider_edits.length ?? 0) > 0 && <label className="mt-4 block text-xs font-medium">Summary of changes (optional)<textarea value={changeSummary} onChange={(e) => { setChangeSummary(e.target.value); setActionError(""); }} className="mt-1 w-full rounded-lg border bg-white px-3 py-2" rows={2} placeholder="Briefly describe the corrections made before resubmission" /></label>}
        <label className="mt-4 block text-xs font-medium">Approval note (optional)<textarea value={approvalNote} onChange={(e) => { setApprovalNote(e.target.value); setActionError(""); }} className="mt-1 w-full rounded-lg border bg-white px-3 py-2" rows={2} /></label>
        <label className="mt-4 flex items-start gap-2 text-sm"><input type="checkbox" checked={attestation} onChange={(e) => setAttestation(e.target.checked)} className="mt-1" /><span>I attest that I reviewed this return and that the information supplied is accurate to the best of my knowledge. Any blank indicators will remain visible to NCA.</span></label>
        {actionError && <p role="alert" className="mt-3 text-xs text-red-700">{actionError}</p>}
        <div className="mt-4 flex justify-end gap-2"><button type="button" onClick={() => setApprovalOpen(false)} className="rounded-lg border px-4 py-2 text-xs">Cancel</button><button type="button" disabled={!attestation || !completion?.transition_ready} onClick={()=>setOfficialConfirmOpen(true)} className="rounded-lg bg-[#001836] px-5 py-2 text-xs font-semibold text-white disabled:opacity-50">Submit officially to NCA</button></div>
      </div>}

      {officialConfirmOpen&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"><section role="dialog" aria-modal="true" aria-labelledby="official-submit-title" className="w-full max-w-xl overflow-hidden rounded-2xl bg-white shadow-2xl"><header className="border-b bg-[#f7f9fb] px-6 py-5"><div className="flex items-start gap-3"><span className="rounded-full bg-amber-100 p-2 text-amber-700"><AlertTriangle size={20}/></span><div><h2 id="official-submit-title" className="text-lg font-semibold text-[#191c1e]">Confirm official submission to NCA</h2><p className="mt-1 text-sm text-[#737780]">Review these details before creating the official regulatory submission.</p></div></div></header><div className="space-y-4 p-6"><dl className="grid gap-3 rounded-xl border bg-[#fafbfd] p-4 text-sm sm:grid-cols-2"><div><dt className="text-xs font-semibold uppercase text-[#737780]">Form</dt><dd className="mt-1 font-medium">{expected.form_name}</dd></div><div><dt className="text-xs font-semibold uppercase text-[#737780]">Reporting period</dt><dd className="mt-1 font-medium">{expected.period_name}</dd></div><div><dt className="text-xs font-semibold uppercase text-[#737780]">Reference</dt><dd className="mt-1 break-all font-mono text-xs">{submission?.submission_reference||expected.form_reference}</dd></div><div><dt className="text-xs font-semibold uppercase text-[#737780]">Completion</dt><dd className="mt-1 font-medium">{Number(completion?.completion_pct??0).toFixed(0)}%</dd></div><div><dt className="text-xs font-semibold uppercase text-[#737780]">Blank indicators</dt><dd className="mt-1 font-medium">{completion?.missing_indicator_count??0}</dd></div><div><dt className="text-xs font-semibold uppercase text-[#737780]">Open flags</dt><dd className="mt-1 font-medium">{completion?.open_correction_item_count??0}</dd></div></dl>{approvalNote.trim()&&<div><p className="text-xs font-semibold uppercase text-[#737780]">Approval note</p><p className="mt-1 whitespace-pre-wrap rounded-lg border p-3 text-sm">{approvalNote}</p></div>}{changeSummary.trim()&&<div><p className="text-xs font-semibold uppercase text-[#737780]">Change summary</p><p className="mt-1 whitespace-pre-wrap rounded-lg border p-3 text-sm">{changeSummary}</p></div>}<div className="rounded-xl bg-[#fff8e1] p-4 text-sm text-[#6b4800]"><strong>Final confirmation:</strong> You have attested that the information is accurate. Once confirmed, this version will be submitted officially to NCA and cannot continue as an editable provider draft.</div></div><footer className="flex justify-end gap-3 border-t px-6 py-4"><button type="button" disabled={officialSubmitting} onClick={()=>setOfficialConfirmOpen(false)} className="rounded-lg border px-4 py-2 text-sm font-semibold">Go back</button><button type="button" disabled={officialSubmitting} onClick={handleOfficialSubmit} className="rounded-lg bg-[#001836] px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">{officialSubmitting?"Submitting…":"Confirm and submit to NCA"}</button></footer></section></div>}

      {handoffEventId&&submission&&<EmailHandoffModal submissionId={submission.id} eventId={handoffEventId} onClose={()=>setHandoffEventId(null)}/>}

      {(receiptReference || submission?.receipt_reference) && <div className="flex items-center justify-between rounded-xl border border-green-200 bg-green-50 p-4 text-sm"><span>Official receipt: <strong>{receiptReference || submission?.receipt_reference}</strong></span><button onClick={() => import("@/lib/api").then(({downloadAuthenticated}) => downloadAuthenticated(`/submissions/${submission?.id}/receipt/`, {}, `submission-receipt-${submission?.id}.pdf`))} className="font-semibold text-[#0066cc]">Download receipt</button></div>}

      {submission && <section className="rounded-xl border border-[#dce3e9] bg-white p-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div className="flex items-start gap-3">
            <span className="rounded-lg bg-[#e8f1fb] p-2 text-[#004999]"><FileSpreadsheet size={18} aria-hidden="true" /></span>
            <div><h2 className="text-[13px] font-semibold text-[#191c1e]">NCA monthly Excel report</h2>
              <p className="mt-0.5 text-[11px] text-[#737780]">{monthlyReportQ.data?.status === "READY" ? "Generated from the approved provider-specific NCA workbook baseline." : monthlyReportQ.data?.detail || (monthlyReportQ.data?.status === "PREPARING" ? "The submitted report is being prepared." : monthlyReportQ.data?.status === "FAILED" ? monthlyReportQ.data.error_message : "Available after the Provider Approver officially submits to NCA.")}</p>
            </div>
          </div>
          {monthlyReportQ.data?.download_ready ? <button type="button" onClick={() => import("@/lib/api").then(({downloadAuthenticated}) => downloadAuthenticated(`/submissions/${submission.id}/monthly-report/download/`, {}, monthlyReportQ.data?.filename || `monthly-report-${submission.id}.xlsx`))} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#1f7a4d] px-4 py-2 text-[12px] font-semibold text-white"><FileSpreadsheet size={14} /> Download Excel Report</button>
          : monthlyReportQ.data?.status === "PREPARING" ? <span className="inline-flex items-center gap-2 text-[11px] font-medium text-[#004999]"><RefreshCw size={13} className="animate-spin" /> Preparing</span>
          : <span className="rounded-full bg-[#f2f4f6] px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-[#737780]">{monthlyReportQ.data?.status?.replaceAll("_", " ") || "Unavailable"}</span>}
        </div>
      </section>}

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

      {(providerReviewQ.data?.compliance_flags.length ?? 0) > 0 && <section className="rounded-[12px] border border-[#e6e8ea] bg-white p-4">
        <h2 className="text-[13px] font-semibold text-[#191c1e]">Compliance flags</h2><p className="mt-1 text-[11px] text-[#737780]">Flags associated with this submission are shown here.</p>
        <div className="mt-3 space-y-2">{providerReviewQ.data!.compliance_flags.map(flag=><article key={flag.id} className="rounded-lg border border-amber-200 bg-amber-50 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold">{flag.flag_type.replaceAll("_"," ")}</p><span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold">{flag.status.replaceAll("_"," ")}</span></div><p className="mt-1 text-xs text-[#43474f]">{flag.description}</p><p className="mt-2 text-[10px] text-[#737780]">{flag.completion_percentage}% complete · {flag.missing_field_count} missing</p></article>)}</div>
      </section>}

      <section className="rounded-[12px] border border-[#e6e8ea] bg-white p-4">
        <div className="flex items-center justify-between"><div><h2 className="text-[13px] font-semibold text-[#191c1e]">Communication history</h2><p className="mt-1 text-[11px] text-[#737780]">Portal notifications and submission-related correspondence are recorded together.</p></div></div>
        {isApprover&&submission&&<div className="mt-4 rounded-xl border bg-[#f7f9fb] p-3"><label className="text-xs font-semibold" htmlFor="nca-correspondence">Write to NCA</label><textarea id="nca-correspondence" value={correspondenceText} onChange={event=>setCorrespondenceText(event.target.value)} placeholder="Enter the submission-related message to send to NCA." className="mt-2 min-h-24 w-full rounded-lg border bg-white p-3 text-xs"/><div className="mt-2 flex justify-end"><button disabled={!correspondenceText.trim()} onClick={async()=>{const response=await api.post<{event_id:number}>(`/submissions/${submission.id}/communications/send/`,{message:correspondenceText});setCorrespondenceText("");setHandoffEventId(response.event_id);await refreshProviderWorkflow();}} className="rounded-lg bg-[#002d5b] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40">Send internal message</button></div></div>}
        {communicationsQ.isLoading?<p className="mt-3 text-xs text-[#737780]">Loading communication…</p>:(communicationsQ.data?.length??0)===0?<p className="mt-3 rounded-lg bg-[#f7f9fb] p-3 text-xs text-[#737780]">No communication has been recorded for this form yet.</p>:<div className="mt-3 space-y-3">{communicationsQ.data!.map(item=><article key={item.id} className="rounded-lg border p-3"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-[#e8f1fb] px-2 py-0.5 text-[9px] font-semibold text-[#004999]">Internal correspondence</span>{item.submission_version!=null&&<span className="rounded-full bg-[#e8f1fb] px-2 py-0.5 text-[9px] font-semibold text-[#004999]">Version {item.submission_version}</span>}{item.email_handoff&&<span className="rounded-full bg-[#f2f4f6] px-2 py-0.5 text-[9px] font-semibold uppercase text-[#5e6269]">External draft {item.email_handoff.status.toLowerCase()}</span>}<span className="ml-auto text-[10px] text-[#737780]">{new Date(item.created_at).toLocaleString()}</span></div>{item.subject&&<h3 className="mt-2 text-xs font-semibold">{item.subject}</h3>}{item.submission_reference&&<p className="mt-1 font-mono text-[9px] text-[#004999]">{item.submission_reference}</p>}<p className="mt-1 text-[10px] text-[#737780]">From: {item.sender_name || "NCA Data Collection System"}</p>{item.recipients.length>0&&<p className="mt-1 text-[10px] text-[#737780]">To: {item.recipients.map(recipient=>recipient.email).join(", ")}</p>}<p className="mt-2 whitespace-pre-wrap text-[11px] leading-5 text-[#43474f]">{item.body}</p>{item.email_handoff&&submission&&<button type="button" onClick={()=>setHandoffEventId(item.email_handoff!.event)} className="mt-3 rounded-lg border border-[#0066cc] px-3 py-1.5 text-[11px] font-semibold text-[#0066cc]">Open external email draft</button>}</article>)}</div>}
      </section>

      {completion && completion.missing_indicator_count > 0 && (
        <div className="rounded-[8px] border border-[#b9d4ef] bg-[#eef6ff] px-4 py-3 text-[12px] text-[#264f73]">
          {["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "REJECTED", "ARCHIVED"].includes(expected.workflow_status)
            ? `${completion.missing_indicator_count} requested indicator${completion.missing_indicator_count === 1 ? " was" : "s were"} submitted blank and remain visible to reviewers.`
            : `${completion.missing_indicator_count} requested indicator${completion.missing_indicator_count === 1 ? " is" : "s are"} blank. You may continue and submit; reviewers will see these blanks.`}
        </div>
      )}

      {isEditable && completion && !completion.transition_ready && (
        <div className="rounded-[8px] border border-[#e6a5ae] bg-[#fff1f2] px-4 py-3 text-[12px] text-[#8f1d2c]">
          Resolve {completion.blocking_issues.length} error{completion.blocking_issues.length === 1 ? "" : "s"} before submitting.
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
                <button type="button"
                  key={item.id}
                  onClick={() => void leaveForm(`/provider/forms/${item.id}`)}
                  className={`rounded-[8px] border px-3 py-2 text-[12px] transition-colors ${
                    active
                      ? "border-[#0066cc] bg-[#e8f1fb] text-[#004999]"
                      : "border-[#e6e8ea] bg-[#f7f9fb] text-[#43474f] hover:border-[#c3c6d0] hover:bg-white"
                  }`}
                >
                  <span className="font-semibold">{item.form_code}</span>
                  <span className="ml-2 text-[11px] opacity-75">{item.workflow_status.split("_").join(" ")}</span>
                </button>
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
                  onSelect={(sectionCode) => void navigateToSection(sectionCode)}
          completionPct={completion?.completion_pct ?? 0}
        /></div>

        <label className="block lg:hidden">
          <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">Form section</span>
          <select value={activeSection} onChange={(event) => void navigateToSection(event.target.value)} className="w-full rounded-[9px] border border-[#c3c6d0] bg-white px-3 py-2.5 text-[13px] text-[#191c1e]">
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
              registerSaveController={registerSaveController}
              previousValues={providerReviewQ.data?.previous_month?.values ?? {}}
              onSaved={handleSectionSaved}
            />
          )}

          {/* Prev / Next navigation */}
          <div className="flex items-center justify-between mt-8 pt-5 border-t border-[#eceef0]">
            <button
              onClick={() => void navigateToSection(sections[currentSectionIndex - 1]?.section_code)}
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
              onClick={() => void navigateToSection(sections[currentSectionIndex + 1]?.section_code)}
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

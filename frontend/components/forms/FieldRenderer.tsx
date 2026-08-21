"use client";

import { cn } from "@/lib/utils";
import type { FormField, FieldStatus } from "@/lib/types";
import { ChevronDown, Download, FileText, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, downloadAuthenticated } from "@/lib/api";

const FIELD_STATUS_OPTIONS: { value: FieldStatus; label: string }[] = [
  { value: "NOT_APPLICABLE", label: "Not Applicable" },
  { value: "NOT_AVAILABLE", label: "Not Available" },
  { value: "NOT_REQUIRED", label: "Not Required for Provider" },
  { value: "PENDING_CLARIFICATION", label: "Pending Clarification" },
];

interface FieldRendererProps {
  field: FormField;
  value: string;
  valueStatus: FieldStatus | "";
  explanation: string;
  onChange: (value: string, status: FieldStatus | "", explanation: string) => void;
  disabled?: boolean;
  /** Current values for all fields in the section — used to resolve conditional visibility */
  allFieldValues?: Record<number, { value: string }>;
  issues?: string[];
  correctionInstructions?: string[];
  onBlur?: () => void;
  readOnlyPresentation?: boolean;
  previousValue?: string | null;
  submissionId?: number;
}

const inputBase =
  "w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] transition-colors focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20 disabled:bg-[#f2f4f6] disabled:text-[#737780]";

const numericTypes = new Set(["number", "currency", "percentage"]);

export function isNumericFieldType(fieldType: string) {
  return numericTypes.has(fieldType);
}

export function calculateGrowth(current: string, previous: string | null | undefined, fieldType: FormField["field_type"]) {
  if (!numericTypes.has(fieldType) || previous === null || previous === undefined || previous === "") return null;
  const currentNumber = Number(String(current).replaceAll(",", ""));
  const previousNumber = Number(String(previous).replaceAll(",", ""));
  if (!Number.isFinite(currentNumber) || !Number.isFinite(previousNumber) || !current.trim() || previousNumber === 0) return null;
  return ((currentNumber - previousNumber) / previousNumber) * 100;
}

function PreviousAndGrowth({ field, value, previousValue }: { field: FormField; value: string; previousValue?: string | null }) {
  const numeric = isNumericFieldType(field.field_type);
  if (!numeric) return null;
  const previousNumber = previousValue === null || previousValue === undefined || previousValue === ""
    ? null : Number(String(previousValue).replaceAll(",", ""));
  const previousDisplay = previousValue === null || previousValue === undefined || previousValue === ""
    ? "—"
    : numeric && Number.isFinite(previousNumber)
      ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(previousNumber as number)
      : previousValue;
  const growth = calculateGrowth(value, previousValue, field.field_type);
  const growthDisplay = growth === null ? "N/A" : growth === 0 ? "0.00%" : `${growth > 0 ? "↑ +" : "↓ "}${growth.toFixed(2)}%`;
  const growthLabel = growth === null ? "Growth is not applicable" : growth > 0 ? `Growth increased by ${growth.toFixed(2)} percent` : growth < 0 ? `Growth decreased by ${Math.abs(growth).toFixed(2)} percent` : "No percentage growth";
  return <div className="grid grid-cols-2 gap-2" aria-label="Previous entry comparison">
    <div className="rounded-[7px] border border-[#dce3e9] bg-white px-2.5 py-2">
      <p className="text-[9px] font-semibold uppercase tracking-wide text-[#737780]">Previous entry</p>
      <p className="mt-0.5 truncate text-[12px] font-semibold tabular-nums text-[#23364d]" title={String(previousDisplay)}>{previousDisplay}</p>
    </div>
    <div className="rounded-[7px] border border-[#dce3e9] bg-white px-2.5 py-2" aria-label={growthLabel}>
      <p className="text-[9px] font-semibold uppercase tracking-wide text-[#737780]">Growth</p>
      <p className={cn("mt-0.5 text-[12px] font-semibold tabular-nums", growth === null || growth === 0 ? "text-[#5e6269]" : growth > 0 ? "text-[#1f7a4d]" : "text-[#b3261e]")}>{growthDisplay}</p>
    </div>
  </div>;
}

export function DefinitionDisclosure({ definition }: { definition: string }) {
  if (!definition) return null;
  return <details className="group rounded-[7px] border border-[#e6e8ea] bg-white">
    <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-[11px] font-semibold text-[#004999] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]">
      <span>Definition</span><ChevronDown size={13} className="transition-transform group-open:rotate-180" aria-hidden="true" />
    </summary>
    <p className="border-t border-[#eceef0] px-3 py-2.5 text-[11px] leading-relaxed text-[#5e6269] whitespace-pre-wrap break-words">{definition}</p>
  </details>;
}

type FieldAttachment = { id:number; file_name:string; file_size:number; scan_status:string; download_ready:boolean };

function AttachmentInput({ submissionId, field, disabled }: { submissionId?:number; field:FormField; disabled?:boolean }) {
  const [attachment, setAttachment] = useState<FieldAttachment|null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!submissionId) return;
    try { const items = await api.get<FieldAttachment[]>(`/submissions/${submissionId}/field-attachments/${field.id}/`); setAttachment(items[0] ?? null); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Attachment could not be loaded."); }
  }, [submissionId, field.id]);
  useEffect(() => { void load(); }, [load]);
  async function upload(file?:File) {
    if (!file || !submissionId) return;
    setBusy(true); setError("");
    try { const form = new FormData(); form.append("file", file); await api.upload(`/submissions/${submissionId}/field-attachments/${field.id}/`, form); await load(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Attachment upload failed."); }
    finally { setBusy(false); }
  }
  return <div className="rounded-lg border border-dashed border-[#aeb8c2] bg-white p-3">
    {attachment ? <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2"><FileText size={18} className="shrink-0 text-[#0066cc]"/><div className="min-w-0"><p className="truncate text-xs font-semibold">{attachment.file_name}</p><p className="text-[10px] text-[#737780]">{(attachment.file_size/1024).toFixed(1)} KB · {attachment.scan_status.toLowerCase()}</p></div></div>
      {attachment.download_ready&&<button type="button" onClick={()=>downloadAuthenticated(`/submissions/${submissionId}/field-attachments/files/${attachment.id}/download/`,{},attachment.file_name)} className="flex items-center gap-1 text-xs font-semibold text-[#0066cc]"><Download size={13}/>Download</button>}
    </div>:<p className="text-xs text-[#737780]">No document attached.</p>}
    {!disabled&&<label className="mt-3 flex w-fit cursor-pointer items-center gap-2 rounded-lg bg-[#001836] px-3 py-2 text-xs font-semibold text-white"><Upload size={14}/>{busy?"Uploading…":attachment?"Replace attachment":"Choose attachment"}<input type="file" className="hidden" accept=".doc,.docx,.xls,.xlsx,.pdf" disabled={busy} onChange={event=>void upload(event.target.files?.[0])}/></label>}
    <p className="mt-2 text-[10px] text-[#737780]">Word, Excel, or PDF · Maximum 20 MB</p>
    {error&&<p role="alert" className="mt-2 text-xs font-medium text-red-700">{error}</p>}
  </div>;
}

export function FieldRenderer({ field, value, valueStatus, explanation, onChange, disabled, allFieldValues, issues = [], correctionInstructions = [], onBlur, readOnlyPresentation = false, previousValue, submissionId }: FieldRendererProps) {
  // Conditional visibility — hide if parent field's value doesn't match the required value
  if (
    field.conditional_on_field !== null &&
    field.conditional_on_value &&
    allFieldValues
  ) {
    const parentValue = allFieldValues[field.conditional_on_field]?.value ?? "";
    if (parentValue !== field.conditional_on_value) return null;
  }

  const isNonFilled = !!valueStatus && valueStatus !== "PROVIDED" && valueStatus !== "MISSING";

  if (field.field_type === "attachment") {
    return <div className="space-y-2"><div className="flex items-start justify-between gap-2"><p className="text-[13px] font-medium">{field.label}{field.is_required&&<span className="ml-1 text-[#E31937]">*</span>}</p></div><AttachmentInput submissionId={submissionId} field={field} disabled={disabled}/><DefinitionDisclosure definition={field.help_text}/>{issues.map((issue,index)=><p key={index} role="alert" className="text-[11px] font-medium text-[#c0112a]">{issue}</p>)}</div>;
  }

  if (disabled && readOnlyPresentation) {
    const statusLabel = valueStatus ? valueStatus.split("_").join(" ").toLowerCase() : "not provided";
    return (
      <div className="h-full rounded-[10px] border border-[#e6e8ea] bg-[#f9fafb] px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[12px] font-medium leading-snug text-[#43474f]">
            {field.label}{field.unit && <span className="ml-1 font-normal text-[#737780]">({field.unit})</span>}
          </p>
          {field.is_required && <span className="rounded-full bg-[#e8f1fb] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[#004999]">Requested</span>}
        </div>
        {isNumericFieldType(field.field_type) && <div className="mt-3"><PreviousAndGrowth field={field} value={value} previousValue={previousValue} /></div>}
        <p className="mt-2 whitespace-pre-wrap break-words text-[14px] font-medium text-[#191c1e]">
          {value || <span className="font-normal italic text-[#8a8f98]">— Not provided</span>}
        </p>
        {isNonFilled && <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-[#7a5c00]">{statusLabel}</p>}
        {explanation && <p className="mt-2 border-l-2 border-[#ffd100] pl-2 text-[11px] text-[#5e6269]">{explanation}</p>}
        <div className="mt-3"><DefinitionDisclosure definition={field.help_text} /></div>
        {correctionInstructions.map((instruction, index) => <p key={index} className="mt-2 rounded-md bg-[#fff3bf] px-2 py-1.5 text-[11px] text-[#7a5c00]">Correction: {instruction}</p>)}
        {issues.map((issue, index) => <p key={index} role="alert" className="mt-1 text-[11px] font-medium text-[#c0112a]">{issue}</p>)}
      </div>
    );
  }

  function handleValueChange(newVal: string) {
    onChange(newVal, newVal ? "PROVIDED" : "MISSING", explanation);
  }

  function handleStatusChange(newStatus: FieldStatus | "") {
    onChange(newStatus ? "" : value, newStatus || (value ? "PROVIDED" : "MISSING"), newStatus ? explanation : "");
  }

  return (
    <div className="space-y-1.5" onBlur={onBlur}>
      {/* Label */}
      <div className="flex items-start justify-between gap-2">
        <label className="text-[13px] font-medium text-[#191c1e] leading-snug">
          {field.label}
          {field.unit && (
            <span className="ml-1 text-[11px] font-normal text-[#737780]">({field.unit})</span>
          )}
          {field.is_required && (
            <span className="ml-1 text-[#E31937]" aria-label="required">*</span>
          )}
        </label>
        {/* Non-filled status selector */}
        {field.is_required && (
          <select
            value={isNonFilled ? valueStatus : ""}
            onChange={(e) => handleStatusChange(e.target.value as FieldStatus | "")}
            disabled={disabled}
            className="shrink-0 rounded-[6px] border border-[#c3c6d0] bg-white px-2 py-1 text-[11px] text-[#43474f] focus:outline-none focus:border-[#0066cc]"
            title="Mark as non-filled"
          >
            <option value="">— Status</option>
            {FIELD_STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        )}
      </div>

      {isNumericFieldType(field.field_type) && <PreviousAndGrowth field={field} value={value} previousValue={previousValue} />}
      {correctionInstructions.map((instruction, index) => <p key={index} className="rounded-md bg-[#fff3bf] px-2 py-1.5 text-[11px] text-[#7a5c00]">Correction: {instruction}</p>)}
      {issues.map((issue, index) => <p key={index} role="alert" className="text-[11px] font-medium text-[#c0112a]">{issue}</p>)}

      {/* Input — hidden if non-filled status is set */}
      {!isNonFilled && (
        <>
          {field.field_type === "textarea" && (
            <textarea
              value={value}
              onChange={(e) => handleValueChange(e.target.value)}
              disabled={disabled}
              rows={3}
              className={cn(inputBase, "resize-y")}
              placeholder={`Enter ${field.label.toLowerCase()}`}
            />
          )}

          {field.field_type === "boolean" && (
            <div className="flex gap-4">
              {["Yes", "No"].map((opt) => (
                <label key={opt} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name={`field-${field.id}`}
                    value={opt}
                    checked={value === opt}
                    onChange={() => handleValueChange(opt)}
                    disabled={disabled}
                    className="accent-[#0066cc]"
                  />
                  <span className="text-[13px] text-[#191c1e]">{opt}</span>
                </label>
              ))}
            </div>
          )}

          {field.field_type === "select" && (
            <select
              value={value}
              onChange={(e) => handleValueChange(e.target.value)}
              disabled={disabled}
              className={inputBase}
            >
              <option value="">Select an option</option>
              {field.options?.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          )}

          {field.field_type === "declaration" && (
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={value === "true"}
                onChange={(e) => handleValueChange(e.target.checked ? "true" : "")}
                disabled={disabled}
                className="mt-0.5 h-4 w-4 accent-[#0066cc]"
              />
              <span className="text-[13px] text-[#191c1e]">
                I confirm the information provided is accurate and complete.
              </span>
            </label>
          )}

          {field.field_type === "formula" && (
            <div className={cn(inputBase, "bg-[#f2f4f6] text-[#43474f] cursor-not-allowed")}>
              {value || <span className="text-[#737780]">Calculated automatically</span>}
            </div>
          )}

          {["text", "number", "currency", "percentage", "date", "coordinate", "multiselect"].includes(field.field_type) && (
            <input
              type={
                field.field_type === "number" || field.field_type === "currency" || field.field_type === "percentage"
                  ? "number"
                  : field.field_type === "date"
                  ? "date"
                  : "text"
              }
              value={value}
              onChange={(e) => handleValueChange(e.target.value)}
              disabled={disabled}
              step={field.field_type === "percentage" ? "0.01" : undefined}
              className={inputBase}
              placeholder={
                field.field_type === "currency"
                  ? "0.00"
                  : field.field_type === "percentage"
                  ? "0.00"
                  : field.field_type === "coordinate"
                  ? "e.g. 5.603717"
                  : `Enter ${field.label.toLowerCase()}`
              }
            />
          )}
        </>
      )}

      {/* Explanation field for non-filled statuses */}
      {isNonFilled && (
        <textarea
          value={explanation}
          onChange={(e) => onChange(value, valueStatus, e.target.value)}
          disabled={disabled}
          rows={2}
          className={cn(inputBase, "resize-none border-[#ffd100] bg-[#fff3bf]/40")}
          placeholder="Provide the required explanation"
          aria-required="true"
        />
      )}
      <DefinitionDisclosure definition={field.help_text} />
    </div>
  );
}

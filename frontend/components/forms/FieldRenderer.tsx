"use client";

import { cn } from "@/lib/utils";
import type { FormField, FieldStatus } from "@/lib/types";

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
}

const inputBase =
  "w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] transition-colors focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20 disabled:bg-[#f2f4f6] disabled:text-[#737780]";

export function FieldRenderer({ field, value, valueStatus, explanation, onChange, disabled }: FieldRendererProps) {
  const isNonFilled = !!valueStatus && valueStatus !== "PROVIDED" && valueStatus !== "MISSING";

  function handleValueChange(newVal: string) {
    onChange(newVal, newVal ? "PROVIDED" : "MISSING", explanation);
  }

  function handleStatusChange(newStatus: FieldStatus | "") {
    onChange(value, newStatus || "MISSING", explanation);
  }

  return (
    <div className="space-y-1.5">
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

      {/* Help text */}
      {field.help_text && (
        <p className="text-[11px] text-[#737780] leading-snug">{field.help_text}</p>
      )}

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
          placeholder="Provide a brief explanation (optional but recommended)"
        />
      )}
    </div>
  );
}

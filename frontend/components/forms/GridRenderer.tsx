"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FormGrid, FieldStatus } from "@/lib/types";

interface CellValue {
  grid_row_id: string;
  grid_column_id: number;
  value: string;
  value_status: FieldStatus | "";
  explanation?: string;
}

interface GridRendererProps {
  grid: FormGrid;
  values: CellValue[];
  onChange: (values: CellValue[]) => void;
  disabled?: boolean;
  issues?: Array<{ targetId:string; message:string }>;
  correctionInstructions?: Array<{ targetId:string; instruction:string }>;
  readOnlyPresentation?: boolean;
  sectionCode: string;
  previousValues?: Record<string, string | null>;
}

const cellInput =
  "w-full rounded-[4px] border-0 bg-transparent px-2 py-1.5 text-[12px] text-[#191c1e] placeholder:text-[#c3c6d0] focus:outline-none focus:ring-1 focus:ring-[#0066cc]/30 tabular-nums";

const nonFilled = ["NOT_APPLICABLE", "NOT_AVAILABLE", "NOT_REQUIRED"];

function numericGrowth(current: string | undefined, previous: string | null | undefined, fieldType: string) {
  if (!["number", "currency", "percentage"].includes(fieldType) || previous == null || previous === "" || !current) return null;
  const currentNumber = Number(current.replaceAll(",", ""));
  const previousNumber = Number(previous.replaceAll(",", ""));
  if (!Number.isFinite(currentNumber) || !Number.isFinite(previousNumber) || previousNumber === 0) return null;
  return ((currentNumber - previousNumber) / previousNumber) * 100;
}

export function GridRenderer({ grid, values, onChange, disabled, issues = [], correctionInstructions = [], readOnlyPresentation = false, sectionCode, previousValues = {} }: GridRendererProps) {
  const [repeatableRows, setRepeatableRows] = useState<string[]>(() => {
    if (grid.row_mode === "FIXED") return [];
    const ids = [...new Set(values.map((value) => value.grid_row_id).filter(Boolean))];
    return ids.length ? ids : [crypto.randomUUID()];
  });

  useEffect(() => {
    if (grid.row_mode === "FIXED") return;
    const ids = [...new Set(values.map((value) => value.grid_row_id).filter(Boolean))];
    if (ids.length) setRepeatableRows(ids);
  }, [grid.row_mode, values]);

  const rows = grid.row_mode === "FIXED"
    ? (grid.fixed_rows ?? []).map((row) => ({ id: String(row.id), label: row.row_label }))
    : (disabled && readOnlyPresentation && values.length === 0 ? [] : repeatableRows)
        .map((id, index) => ({ id, label: `Row ${index + 1}` }));

  function cell(rowId: string, columnId: number) {
    return values.find((value) => value.grid_row_id === rowId && value.grid_column_id === columnId);
  }

  function replaceCell(rowId: string, columnId: number, replacement: CellValue) {
    onChange([
      ...values.filter((value) => !(value.grid_row_id === rowId && value.grid_column_id === columnId)),
      replacement,
    ]);
  }

  function setValue(rowId: string, columnId: number, value: string) {
    replaceCell(rowId, columnId, {
      grid_row_id: rowId, grid_column_id: columnId, value,
      value_status: value ? "PROVIDED" : "MISSING", explanation: "",
    });
  }

  function setStatus(rowId: string, columnId: number, status: FieldStatus | "") {
    const current = cell(rowId, columnId);
    replaceCell(rowId, columnId, {
      grid_row_id: rowId, grid_column_id: columnId,
      value: status ? "" : current?.value ?? "",
      value_status: status || (current?.value ? "PROVIDED" : "MISSING"),
      explanation: current?.explanation ?? "",
    });
  }

  function setExplanation(rowId: string, columnId: number, explanation: string) {
    const current = cell(rowId, columnId);
    replaceCell(rowId, columnId, {
      grid_row_id: rowId, grid_column_id: columnId, value: "",
      value_status: current?.value_status || "NOT_AVAILABLE", explanation,
    });
  }

  function removeRow(rowId: string) {
    setRepeatableRows((current) => current.filter((id) => id !== rowId));
    onChange(values.filter((value) => value.grid_row_id !== rowId));
  }

  if (disabled && readOnlyPresentation) {
    return (
      <div className="overflow-hidden rounded-[10px] border border-[#e6e8ea] bg-white">
        <div className="border-b border-[#e6e8ea] bg-[#f2f4f6] px-4 py-3">
          <p className="text-[13px] font-semibold text-[#191c1e]">{grid.title}</p>
          {grid.instructions && <p className="mt-1 text-[11px] text-[#737780]">{grid.instructions}</p>}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead><tr className="bg-[#f9fafb]">
              <th className="min-w-[130px] px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-[#737780]">Item</th>
              {grid.columns.map((column) => <th key={column.id} className="min-w-[140px] px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-[#737780]">{column.label}{column.unit ? ` (${column.unit})` : ""}</th>)}
            </tr></thead>
            <tbody>{rows.length ? rows.map((row) => <tr key={row.id} className="border-t border-[#eceef0]">
              <td className="px-3 py-2 text-[11px] font-medium text-[#43474f]">{row.label}</td>
              {grid.columns.map((column) => {
                const current = cell(row.id, column.id);
                const previousKey = `grid:${sectionCode}:${grid.grid_code}:${row.label}:${column.column_code}`.toLowerCase();
                const previous = previousValues[previousKey];
                const growth = numericGrowth(current?.value, previous, column.field_type);
                return <td key={column.id} className="px-3 py-2 text-[12px] text-[#191c1e]">
                  {current?.value || current?.explanation || <span className="italic text-[#8a8f98]">— Not provided</span>}
                  {current?.value_status && !["PROVIDED", "MISSING"].includes(current.value_status) && <span className="mt-0.5 block text-[9px] uppercase tracking-wide text-[#7a5c00]">{current.value_status.split("_").join(" ")}</span>}
                  <span className="mt-1 block text-[9px] text-[#737780]">Previous: {previous ?? "—"} · Growth: {growth === null ? "N/A" : `${growth > 0 ? "↑ +" : growth < 0 ? "↓ " : ""}${growth.toFixed(2)}%`}</span>
                </td>;
              })}
            </tr>) : <tr><td colSpan={grid.columns.length + 1} className="px-4 py-8 text-center text-[12px] italic text-[#8a8f98]">No rows provided</td></tr>}</tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[8px] border border-[#e6e8ea]">
      <div className="border-b border-[#e6e8ea] bg-[#f2f4f6] px-4 py-2.5">
        <p className="text-[12px] font-semibold text-[#43474f]">{grid.title}</p>
        {grid.instructions && <p className="mt-0.5 text-[11px] text-[#737780]">{grid.instructions}</p>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e6e8ea] bg-[#f7f9fb]">
              <th className="min-w-[140px] px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[#737780]">
                {grid.row_mode === "FIXED" ? "Item" : ""}
              </th>
              {grid.columns.map((column) => (
                <th key={column.id} className="min-w-[145px] px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-[0.04em] text-[#737780]">
                  {column.label}{column.unit && <span className="ml-1 text-[10px] font-normal normal-case">({column.unit})</span>}
                  {column.is_required && <span className="ml-0.5 text-[#E31937]">*</span>}
                </th>
              ))}
              {grid.row_mode === "REPEATABLE" && !disabled && <th className="w-8 px-2" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id} className={cn("border-b border-[#eceef0] last:border-0", index % 2 ? "bg-[#f7f9fb]" : "bg-white")}>
                <td className="whitespace-nowrap px-3 py-1.5 text-[12px] font-medium text-[#43474f]">{row.label}</td>
                {grid.columns.map((column) => {
                  const current = cell(row.id, column.id);
                  const hasNonFilledStatus = nonFilled.includes(current?.value_status ?? "");
                  const targetId = `${grid.id}:${row.id}:${column.id}`;
                  const previousKey = `grid:${sectionCode}:${grid.grid_code}:${row.label}:${column.column_code}`.toLowerCase();
                  const previous = previousValues[previousKey];
                  const growth = numericGrowth(current?.value, previous, column.field_type);
                  const cellIssues = issues.filter((item) => item.targetId === targetId);
                  const cellCorrections = correctionInstructions.filter((item) => item.targetId === targetId);
                  return (
                    <td key={column.id} className="px-1 py-0.5 text-right">
                      {hasNonFilledStatus ? (
                        <input value={current?.explanation ?? ""} onChange={(event) => setExplanation(row.id, column.id, event.target.value)}
                          disabled={disabled} className={cn(cellInput, "text-left bg-[#fff3bf]/40")} placeholder="Required explanation"
                          aria-label={`${column.label} explanation`} />
                      ) : (
                        <input type={["number", "currency", "percentage"].includes(column.field_type) ? "number" : "text"}
                          value={current?.value ?? ""} onChange={(event) => setValue(row.id, column.id, event.target.value)}
                          disabled={disabled} step={column.field_type === "percentage" ? "0.01" : undefined}
                          className={cn(cellInput, "text-right")} placeholder="—" />
                      )}
                      <p className="px-1 pb-1 text-left text-[9px] text-[#737780]">Previous: {previous ?? "—"} · Growth: {growth === null ? "N/A" : `${growth > 0 ? "↑ +" : growth < 0 ? "↓ " : ""}${growth.toFixed(2)}%`}</p>
                      {column.is_required && !disabled && (
                        <select value={hasNonFilledStatus ? current?.value_status : ""}
                          onChange={(event) => setStatus(row.id, column.id, event.target.value as FieldStatus | "")}
                          className="mb-1 w-full rounded border border-[#e6e8ea] bg-white px-1 py-0.5 text-[10px] text-[#737780]"
                          aria-label={`${column.label} value status`}>
                          <option value="">Value provided</option>
                          <option value="NOT_APPLICABLE">Not applicable</option>
                          <option value="NOT_AVAILABLE">Not available</option>
                          <option value="NOT_REQUIRED">Not required</option>
                        </select>
                      )}
                      {cellCorrections.map((item, correctionIndex) => <p key={correctionIndex} className="px-1 text-left text-[10px] text-[#7a5c00]">Correction: {item.instruction}</p>)}
                      {cellIssues.map((item, issueIndex) => <p key={issueIndex} role="alert" className="px-1 text-left text-[10px] font-medium text-[#c0112a]">{item.message}</p>)}
                    </td>
                  );
                })}
                {grid.row_mode === "REPEATABLE" && !disabled && (
                  <td className="px-2 py-1"><button type="button" onClick={() => removeRow(row.id)}
                    className="flex h-6 w-6 items-center justify-center rounded text-[#737780] hover:bg-[#ffe8e8] hover:text-[#E31937]"
                    aria-label="Remove row"><Trash2 size={12} /></button></td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {grid.row_mode === "REPEATABLE" && !disabled && (
        <div className="border-t border-[#eceef0] px-4 py-2.5">
          <button type="button" onClick={() => setRepeatableRows((current) => [...current, crypto.randomUUID()])}
            className="flex items-center gap-1.5 text-[12px] font-medium text-[#0066cc] hover:text-[#002d5b]">
            <Plus size={13} /> Add row
          </button>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FormGrid, FieldStatus } from "@/lib/types";

interface CellValue {
  grid_row_id: string;
  grid_column_id: number;
  value: string;
  value_status: FieldStatus | "";
}

interface GridRendererProps {
  grid: FormGrid;
  values: CellValue[];
  onChange: (values: CellValue[]) => void;
  disabled?: boolean;
}

const cellInput =
  "w-full border-0 bg-transparent px-2 py-1.5 text-[12px] text-[#191c1e] placeholder:text-[#c3c6d0] focus:outline-none focus:ring-1 focus:ring-[#0066cc]/30 rounded-[4px] tabular-nums";

export function GridRenderer({ grid, values, onChange, disabled }: GridRendererProps) {
  const [repeatableRows, setRepeatableRows] = useState<string[]>(() => {
    if (grid.row_mode === "FIXED") return [];
    const rowIds = [...new Set(values.map((v) => v.grid_row_id))];
    return rowIds.length ? rowIds : [crypto.randomUUID()];
  });

  const rows = grid.row_mode === "FIXED"
    ? (grid.fixed_rows ?? []).map((r) => ({ id: String(r.id), label: r.row_label }))
    : repeatableRows.map((id, i) => ({ id, label: `Row ${i + 1}` }));

  function getCellValue(rowId: string, colId: number) {
    return values.find((v) => v.grid_row_id === rowId && v.grid_column_id === colId)?.value ?? "";
  }

  function setCellValue(rowId: string, colId: number, newVal: string) {
    const next = values.filter((v) => !(v.grid_row_id === rowId && v.grid_column_id === colId));
    next.push({ grid_row_id: rowId, grid_column_id: colId, value: newVal, value_status: newVal ? "PROVIDED" : "MISSING" });
    onChange(next);
  }

  function addRow() {
    setRepeatableRows((r) => [...r, crypto.randomUUID()]);
  }

  function removeRow(rowId: string) {
    setRepeatableRows((r) => r.filter((id) => id !== rowId));
    onChange(values.filter((v) => v.grid_row_id !== rowId));
  }

  return (
    <div className="rounded-[8px] border border-[#e6e8ea] overflow-hidden">
      {grid.title && (
        <div className="px-4 py-2.5 bg-[#f2f4f6] border-b border-[#e6e8ea]">
          <p className="text-[12px] font-semibold text-[#43474f]">{grid.title}</p>
          {grid.instructions && (
            <p className="text-[11px] text-[#737780] mt-0.5">{grid.instructions}</p>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e6e8ea] bg-[#f7f9fb]">
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[#737780] min-w-[140px]">
                {grid.row_mode === "FIXED" ? "Region" : ""}
              </th>
              {grid.columns.map((col) => (
                <th key={col.id} className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-[0.04em] text-[#737780] min-w-[120px]">
                  {col.label}
                  {col.unit && <span className="ml-1 text-[10px] font-normal normal-case text-[#737780]">({col.unit})</span>}
                  {col.is_required && <span className="ml-0.5 text-[#E31937]">*</span>}
                </th>
              ))}
              {grid.row_mode === "REPEATABLE" && !disabled && (
                <th className="w-8 px-2" />
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-[#eceef0] last:border-0",
                  i % 2 === 0 ? "bg-white" : "bg-[#f7f9fb]"
                )}
              >
                <td className="px-3 py-1.5 text-[12px] font-medium text-[#43474f] whitespace-nowrap">
                  {row.label}
                </td>
                {grid.columns.map((col) => (
                  <td key={col.id} className="px-1 py-0.5 text-right">
                    <input
                      type={["number", "currency", "percentage"].includes(col.field_type) ? "number" : "text"}
                      value={getCellValue(row.id, col.id)}
                      onChange={(e) => setCellValue(row.id, col.id, e.target.value)}
                      disabled={disabled}
                      step={col.field_type === "percentage" ? "0.01" : undefined}
                      className={cn(cellInput, "text-right")}
                      placeholder="—"
                    />
                  </td>
                ))}
                {grid.row_mode === "REPEATABLE" && !disabled && (
                  <td className="px-2 py-1">
                    <button
                      onClick={() => removeRow(row.id)}
                      className="flex h-6 w-6 items-center justify-center rounded text-[#737780] hover:bg-[#ffe8e8] hover:text-[#E31937] transition-colors"
                      aria-label="Remove row"
                    >
                      <Trash2 size={12} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {grid.row_mode === "REPEATABLE" && !disabled && (
        <div className="px-4 py-2.5 border-t border-[#eceef0]">
          <button
            onClick={addRow}
            className="flex items-center gap-1.5 text-[12px] font-medium text-[#0066cc] hover:text-[#002d5b] transition-colors"
          >
            <Plus size={13} />
            Add row
          </button>
        </div>
      )}
    </div>
  );
}

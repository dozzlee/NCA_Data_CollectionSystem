"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, downloadAuthenticated } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime } from "@/lib/utils";
import { Download, FileText } from "lucide-react";

interface ExportLog {
  id: number;
  export_type: "CSV" | "XLSX" | "PDF";
  filters: Record<string, string>;
  generated_by: string;
  generated_at: string;
  row_count: number;
}

export default function ExportsPage() {
  const [exporting, setExporting] = useState<"CSV" | "PDF" | null>(null);
  const [period, setPeriod] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const logsQ = useQuery({ queryKey: ["export-logs"], queryFn: () => api.get<ExportLog[]>("/exports/") });

  async function handleExport(format: "CSV" | "PDF") {
    setExporting(format);
    setMessage(null);
    try {
      await downloadAuthenticated(
        `/exports/${format.toLowerCase()}/`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filters: { period } }) },
        `nca_export_${new Date().toISOString().slice(0, 10)}.${format.toLowerCase()}`,
      );
      setMessage(`${format} downloaded successfully.`);
      logsQ.refetch();
    } catch {
      setMessage("Export failed. Check the selected period and try again.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="max-w-[800px] space-y-6">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]">Exports</h1>
        <p className="mt-0.5 text-[13px] text-[#737780]">Generate approved-only CSV or PDF exports. Every export is logged and audited.</p>
      </div>

      <div className="space-y-5 rounded-[16px] border border-[#e6e8ea] bg-white p-6 shadow-[0_2px_8px_rgba(0,45,91,0.05)]">
        <div>
          <p className="text-[14px] font-semibold text-[#191c1e]">Approved operational data</p>
          <p className="mt-1 text-[12px] leading-5 text-[#43474f]">
            Only NCA-approved submission versions are included. CSV contains the complete canonical long/narrow schema; PDF provides a paginated operational table.
          </p>
        </div>
        <div className="max-w-xs">
          <label htmlFor="export-period" className="mb-1.5 block text-[12px] font-medium text-[#43474f]">Period ID</label>
          <input id="export-period" type="number" value={period} onChange={(event) => setPeriod(event.target.value)}
            placeholder="Leave blank for all periods"
            className="w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none" />
        </div>
        <div className="rounded-[8px] bg-[#f2f4f6] px-4 py-3 text-[11px] leading-relaxed text-[#737780]">
          Provider · Form and version · Period · Submission metadata · Scalar/grid values · Status and explanation · Review and compliance context
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={() => handleExport("CSV")} disabled={Boolean(exporting)}
            className="flex items-center gap-2 rounded-[8px] bg-[#002d5b] px-5 py-2.5 text-[13px] font-semibold text-white disabled:opacity-60">
            <Download size={14} />{exporting === "CSV" ? "Generating…" : "Download CSV"}
          </button>
          <button onClick={() => handleExport("PDF")} disabled={Boolean(exporting)}
            className="flex items-center gap-2 rounded-[8px] border border-[#002d5b] bg-white px-5 py-2.5 text-[13px] font-semibold text-[#002d5b] disabled:opacity-60">
            <FileText size={14} />{exporting === "PDF" ? "Generating…" : "Download PDF"}
          </button>
          {message && <p className={`text-[12px] font-medium ${message.includes("failed") ? "text-[#E31937]" : "text-[#1f7a4d]"}`}>{message}</p>}
        </div>
      </div>

      <div className="rounded-[16px] border border-[#e6e8ea] bg-white shadow-[0_2px_8px_rgba(0,45,91,0.05)]">
        <div className="border-b border-[#eceef0] px-5 py-4"><p className="text-[13px] font-semibold text-[#191c1e]">Export history</p></div>
        <div className="divide-y divide-[#f2f4f6]">
          {logsQ.isLoading ? Array.from({ length: 4 }).map((_, index) => <div key={index} className="px-5 py-3"><Skeleton className="h-10 w-full" /></div>)
            : !logsQ.data?.length ? <p className="px-5 py-10 text-center text-[13px] text-[#737780]">No exports yet.</p>
            : logsQ.data.map((log) => (
              <div key={log.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[#eceef0]"><FileText size={14} /></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-[#191c1e]">{log.export_type} export · {log.row_count.toLocaleString()} rows</p>
                  <p className="text-[11px] text-[#737780]">by {log.generated_by} · {formatDateTime(log.generated_at)}</p>
                </div>
                {Object.keys(log.filters).some((key) => log.filters[key]) && <span className="text-[10px] text-[#737780]">Filtered</span>}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

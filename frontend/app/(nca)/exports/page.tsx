"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime } from "@/lib/utils";
import { Download, FileText, Clock } from "lucide-react";

interface ExportLog {
  id: number;
  export_type: "CSV" | "PDF";
  filters: Record<string, string>;
  generated_by: string;
  generated_at: string;
  row_count: number;
}

export default function ExportsPage() {
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState({ workflow_status: "", period: "" });
  const [exported, setExported] = useState<string | null>(null);

  const logsQ = useQuery({
    queryKey: ["export-logs"],
    queryFn: () => api.get<ExportLog[]>("/exports/"),
  });

  async function handleExportCSV() {
    setExporting(true);
    setExported(null);
    try {
      const token = document.cookie.match(/access_token=([^;]+)/)?.[1];
      const res = await fetch("/api/v1/exports/csv/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ filters }),
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nca_export_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setExported("CSV downloaded successfully.");
      logsQ.refetch();
    } catch {
      setExported("Export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-[800px]">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Exports</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">Generate CSV exports of submission data. All exports are logged and audited.</p>
      </div>

      {/* Export builder */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-6 space-y-5"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <p className="text-[14px] font-semibold text-[#191c1e]">CSV Export</p>
        <p className="text-[12px] text-[#43474f]">
          Exports in long/narrow format — one row per field value. Suitable for spreadsheet analysis and downstream dashboards.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[12px] font-medium text-[#43474f] mb-1.5">Workflow Status</label>
            <select
              value={filters.workflow_status}
              onChange={(e) => setFilters((f) => ({ ...f, workflow_status: e.target.value }))}
              className="w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]"
            >
              <option value="">All statuses</option>
              <option value="APPROVED">Approved only</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="UNDER_REVIEW">Under Review</option>
            </select>
          </div>
          <div>
            <label className="block text-[12px] font-medium text-[#43474f] mb-1.5">Period ID</label>
            <input
              type="number"
              value={filters.period}
              onChange={(e) => setFilters((f) => ({ ...f, period: e.target.value }))}
              placeholder="Leave blank for all periods"
              className="w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] focus:outline-none focus:border-[#0066cc]"
            />
          </div>
        </div>

        {/* Format note */}
        <div className="rounded-[8px] bg-[#f2f4f6] px-4 py-3">
          <p className="text-[11px] font-semibold text-[#43474f] mb-1">Export columns</p>
          <p className="text-[11px] text-[#737780] leading-relaxed">
            Provider · Form &amp; Period · Submission metadata · Section / Field / Grid info · Value &amp; status · Export audit
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExportCSV}
            disabled={exporting}
            className="flex items-center gap-2 rounded-[8px] bg-[#002d5b] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#001836] disabled:opacity-60 transition-colors"
          >
            <Download size={14} />
            {exporting ? "Generating…" : "Download CSV"}
          </button>
          {exported && (
            <p className={`text-[12px] font-medium ${exported.includes("failed") ? "text-[#E31937]" : "text-[#1f7a4d]"}`}>
              {exported}
            </p>
          )}
        </div>
      </div>

      {/* Export log */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <div className="px-5 py-4 border-b border-[#eceef0]">
          <p className="text-[13px] font-semibold text-[#191c1e]">Export History</p>
        </div>
        <div className="divide-y divide-[#f2f4f6]">
          {logsQ.isLoading
            ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="px-5 py-3"><Skeleton className="h-10 w-full" /></div>)
            : !logsQ.data?.length
            ? <p className="px-5 py-10 text-center text-[13px] text-[#737780]">No exports yet.</p>
            : logsQ.data.map((log) => (
                <div key={log.id} className="flex items-center gap-4 px-5 py-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] bg-[#eceef0]">
                    <FileText size={14} className="text-[#43474f]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-medium text-[#191c1e]">
                      {log.export_type} Export · {log.row_count.toLocaleString()} rows
                    </p>
                    <p className="text-[11px] text-[#737780]">
                      by {log.generated_by} · {formatDateTime(log.generated_at)}
                    </p>
                  </div>
                  {Object.keys(log.filters).length > 0 && (
                    <div className="shrink-0 text-right">
                      <p className="text-[10px] text-[#737780]">Filtered</p>
                    </div>
                  )}
                </div>
              ))
          }
        </div>
      </div>
    </div>
  );
}

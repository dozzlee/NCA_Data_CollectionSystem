"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, Clock, FileStack, Play } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/utils";
import type { Frequency, PaginatedResponse, ReportingPeriod } from "@/lib/types";

type PeriodStatus = ReportingPeriod["status"];

const FREQUENCIES: Frequency[] = ["MONTHLY", "SEMI_ANNUAL", "ANNUAL"];
const STATUSES: PeriodStatus[] = ["DRAFT", "ACTIVE", "CLOSED"];

function statusVariant(status: PeriodStatus) {
  if (status === "ACTIVE") return "success";
  if (status === "CLOSED") return "muted";
  return "warning";
}

function frequencyLabel(frequency: Frequency) {
  return frequency.replace("_", " ").toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function PeriodsPage() {
  const qc = useQueryClient();
  const [frequency, setFrequency] = useState<Frequency | "">("");
  const [status, setStatus] = useState<PeriodStatus | "">("");

  const params = useMemo(() => {
    const qs = new URLSearchParams();
    if (frequency) qs.set("frequency", frequency);
    if (status) qs.set("status", status);
    return qs.toString();
  }, [frequency, status]);

  const periodsQ = useQuery({
    queryKey: ["periods", params],
    queryFn: () => api.get<PaginatedResponse<ReportingPeriod>>(`/periods/${params ? `?${params}` : ""}`),
  });

  const activatePeriod = useMutation({
    mutationFn: (periodId: number) => api.post(`/periods/${periodId}/activate/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["periods"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["expected-submissions"] });
    },
  });

  const periods = periodsQ.data?.results ?? [];
  const active = periods.filter((p) => p.status === "ACTIVE").length;
  const closed = periods.filter((p) => p.status === "CLOSED").length;
  const expected = periods.reduce((sum, p) => sum + (p.expected_count ?? 0), 0);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Reporting Periods</h1>
        <p className="text-[13px] text-[#737780] mt-0.5">Open windows, due dates, assigned providers, and generated expected submissions</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Periods", value: periodsQ.data?.count ?? 0, icon: CalendarClock, color: "#0066cc" },
          { label: "Active", value: active, icon: Clock, color: "#1f7a4d" },
          { label: "Expected Returns", value: expected, icon: FileStack, color: "#002d5b" },
          { label: "Closed", value: closed, icon: CheckCircle2, color: "#737780" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-[16px] bg-white border border-[#e6e8ea] p-5"
            style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{label}</p>
              <div className="h-8 w-8 flex items-center justify-center rounded-[8px]" style={{ background: color + "18" }}>
                <Icon size={14} style={{ color }} />
              </div>
            </div>
            {periodsQ.isLoading ? <Skeleton className="h-8 w-12" /> : (
              <p className="text-[28px] font-semibold tabular-nums text-[#191c1e]">{value}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency | "")}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All frequencies</option>
          {FREQUENCIES.map((f) => <option key={f} value={f}>{frequencyLabel(f)}</option>)}
        </select>

        <select value={status} onChange={(e) => setStatus(e.target.value as PeriodStatus | "")}
          className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        {periodsQ.data && <p className="ml-auto text-[12px] text-[#737780]">{periodsQ.data.count} results</p>}
      </div>

      <div className="rounded-[16px] bg-white border border-[#e6e8ea] overflow-hidden"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#eceef0] bg-[#f7f9fb]">
                {["Period", "Frequency", "Window", "Assignments", "Expected", "Status", ""].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periodsQ.isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-[#eceef0]">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-5 py-3"><Skeleton className="h-4 w-full max-w-[130px]" /></td>
                    ))}
                  </tr>
                ))
              ) : !periods.length ? (
                <tr><td colSpan={7} className="px-5 py-14 text-center text-[13px] text-[#737780]">No periods match the current filters.</td></tr>
              ) : periods.map((period) => (
                <tr key={period.id} className="border-b border-[#eceef0] last:border-0 hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3">
                    <p className="text-[13px] font-medium text-[#191c1e] max-w-[220px] truncate">{period.name}</p>
                    <p className="text-[11px] text-[#737780]">{period.year}{period.month ? ` / ${period.month}` : ""}</p>
                  </td>
                  <td className="px-5 py-3 text-[12px] text-[#43474f]">{frequencyLabel(period.frequency)}</td>
                  <td className="px-5 py-3">
                    <p className="text-[12px] tabular-nums text-[#43474f]">{formatDate(period.opens_at)} - {formatDate(period.due_at)}</p>
                    <p className="text-[11px] text-[#737780]">Due state derived per submission</p>
                  </td>
                  <td className="px-5 py-3">
                    <p className="text-[12px] tabular-nums text-[#43474f]">{period.assigned_provider_count ?? 0} providers</p>
                    <p className="text-[11px] tabular-nums text-[#737780]">{period.form_template_count ?? 0} forms</p>
                  </td>
                  <td className="px-5 py-3 text-[12px] tabular-nums text-[#43474f]">{period.expected_count ?? 0}</td>
                  <td className="px-5 py-3"><Badge variant={statusVariant(period.status)}>{period.status}</Badge></td>
                  <td className="px-5 py-3">
                    {period.status === "DRAFT" ? (
                      <button
                        onClick={() => activatePeriod.mutate(period.id)}
                        disabled={activatePeriod.isPending}
                        className="inline-flex items-center gap-1.5 rounded-[8px] bg-[#002d5b] px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-[#001836] disabled:opacity-50 transition-colors"
                      >
                        <Play size={12} /> Activate
                      </button>
                    ) : (
                      <span className="text-[11px] text-[#737780]">
                        {period.status === "ACTIVE" ? "Generated" : "Closed"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

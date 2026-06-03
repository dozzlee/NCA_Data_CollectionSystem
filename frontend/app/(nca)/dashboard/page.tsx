"use client";

import {
  useDashboardSummary,
  useStatusDonut,
  useCategoryCompletion,
  useSubmissionTrend,
  useOverdueByForm,
  useExpectedSubmissions,
} from "@/hooks/useDashboard";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate, WORKFLOW_LABELS, STATUS_CHART_COLORS, CHART_COLORS, PROVIDER_CATEGORY_LABELS } from "@/lib/utils";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from "recharts";
import { AlertTriangle, CheckCircle2, Clock, FileStack } from "lucide-react";
import { useState } from "react";
import type { WorkflowStatus, DueState } from "@/lib/types";

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  accent,
  icon: Icon,
  loading,
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent: string;
  icon: React.ElementType;
  loading?: boolean;
}) {
  return (
    <div className="rounded-[16px] bg-white border border-[#e6e8ea] p-5 flex flex-col gap-4"
      style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.06)" }}>
      <div className="flex items-start justify-between">
        <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-[#737780]">{label}</p>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px]"
          style={{ background: accent + "18" }}>
          <Icon size={15} style={{ color: accent }} />
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-8 w-20" />
      ) : (
        <div>
          <p className="text-[32px] font-semibold leading-none text-[#191c1e] tabular-nums"
            style={{ letterSpacing: "-0.02em" }}>
            {value}
          </p>
          {sub && <p className="mt-1 text-[12px] text-[#737780]">{sub}</p>}
        </div>
      )}
    </div>
  );
}

// ─── Chart Card ──────────────────────────────────────────────────────────────

function ChartCard({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-[16px] bg-white border border-[#e6e8ea] p-5 flex flex-col gap-4 ${className}`}
      style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.06)" }}>
      <p className="text-[13px] font-semibold text-[#191c1e]">{title}</p>
      {children}
    </div>
  );
}

// ─── Custom tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[8px] bg-white border border-[#e6e8ea] px-3 py-2 shadow-card text-[12px]">
      {label && <p className="font-semibold text-[#191c1e] mb-1">{label}</p>}
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <span className="font-semibold">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

// ─── Filters ─────────────────────────────────────────────────────────────────

const WORKFLOW_FILTER_OPTIONS: WorkflowStatus[] = [
  "NOT_STARTED", "DRAFT", "PENDING_APPROVAL", "SUBMITTED",
  "UNDER_REVIEW", "CORRECTION_REQUESTED", "APPROVED", "OVERDUE" as WorkflowStatus,
];

const DUE_STATE_FILTER_OPTIONS: DueState[] = [
  "OPEN", "DUE_SOON", "DUE_TODAY", "OVERDUE",
];

// ─── Dashboard Page ───────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [workflowFilter, setWorkflowFilter] = useState<WorkflowStatus | "">("");
  const [dueFilter, setDueFilter] = useState<DueState | "">("");

  const activeFilters = {
    ...(workflowFilter ? { workflow_status: workflowFilter } : {}),
    ...(dueFilter ? { due_state: dueFilter } : {}),
    ...filters,
  };

  const summary = useDashboardSummary();
  const donut = useStatusDonut();
  const category = useCategoryCompletion();
  const trend = useSubmissionTrend();
  const overdue = useOverdueByForm();
  const submissions = useExpectedSubmissions(activeFilters);

  const donutData = (donut.data ?? []).map((d) => ({
    name: WORKFLOW_LABELS[d.workflow_status as WorkflowStatus] ?? d.workflow_status,
    value: d.count,
    color: STATUS_CHART_COLORS[d.workflow_status as WorkflowStatus] ?? CHART_COLORS.muted,
  }));

  const categoryData = (category.data ?? []).map((d) => ({
    name: PROVIDER_CATEGORY_LABELS[d.category] ?? d.category,
    "Completion %": d.completion_pct,
    total: d.total,
  }));

  const trendData = (trend.data ?? []).map((d) => ({
    month: d.month ? new Date(d.month).toLocaleDateString("en-GB", { month: "short", year: "2-digit" }) : "",
    Submissions: d.count,
  }));

  const overdueData = (overdue.data ?? []).map((d) => ({
    name: d["form_template__form_code"],
    Overdue: d.count,
  }));

  const s = summary.data;
  const loading = summary.isLoading;

  return (
    <div className="space-y-6">

      {/* Page header */}
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>
          Submission Overview
        </h1>
        <p className="text-[13px] text-[#737780] mt-0.5">
          All reporting periods · Updated just now
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Total Expected"
          value={s?.total_expected ?? 0}
          sub={`${s?.not_started ?? 0} not started`}
          accent="#0066cc"
          icon={FileStack}
          loading={loading}
        />
        <StatCard
          label="Submitted"
          value={(s?.submitted ?? 0) + (s?.under_review ?? 0) + (s?.resubmitted ?? 0)}
          sub={`${s?.under_review ?? 0} under review`}
          accent="#1f7a4d"
          icon={CheckCircle2}
          loading={loading}
        />
        <StatCard
          label="Overdue"
          value={s?.overdue ?? 0}
          sub={`${s?.due_soon ?? 0} due soon`}
          accent="#E31937"
          icon={AlertTriangle}
          loading={loading}
        />
        <StatCard
          label="Approved"
          value={s?.approved ?? 0}
          sub={`${s?.completion_pct ?? 0}% completion rate`}
          accent="#002d5b"
          icon={Clock}
          loading={loading}
        />
      </div>

      {/* Charts — 2-column grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* Status donut */}
        <ChartCard title="Submission Status">
          {donut.isLoading ? (
            <Skeleton className="h-56 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={88}
                  paddingAngle={2}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {donutData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  iconSize={8}
                  iconType="circle"
                  formatter={(v) => (
                    <span className="text-[11px] text-[#43474f]">{v}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Completion by category */}
        <ChartCard title="Completion by Provider Category">
          {category.isLoading ? (
            <Skeleton className="h-56 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={categoryData} layout="vertical" barSize={12} margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                <CartesianGrid horizontal={false} stroke="#eceef0" strokeDasharray="0" />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                  tick={{ fontSize: 11, fill: "#737780" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "#43474f" }}
                  axisLine={false}
                  tickLine={false}
                  width={88}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="Completion %" fill={CHART_COLORS.primary} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Submission trend */}
        <ChartCard title="Submission Trend (12 months)">
          {trend.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData} margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke="#eceef0" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: "#737780" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#737780" }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip content={<ChartTooltip />} />
                <Line
                  type="monotone"
                  dataKey="Submissions"
                  stroke={CHART_COLORS.primary}
                  strokeWidth={2}
                  dot={{ r: 3, fill: CHART_COLORS.primary, strokeWidth: 0 }}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Overdue by form type */}
        <ChartCard title="Overdue by Form Type">
          {overdue.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : overdueData.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-[13px] text-[#737780]">
              No overdue submissions
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={overdueData} barSize={28} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke="#eceef0" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "#43474f" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#737780" }}
                  axisLine={false}
                  tickLine={false}
                  width={24}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="Overdue" fill={CHART_COLORS.danger} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Submission list */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.06)" }}>

        {/* Table header + filters */}
        <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-[#eceef0]">
          <h2 className="text-[14px] font-semibold text-[#191c1e] mr-auto">
            Expected Submissions
          </h2>

          <select
            value={workflowFilter}
            onChange={(e) => setWorkflowFilter(e.target.value as WorkflowStatus | "")}
            className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-1.5 text-[12px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]"
          >
            <option value="">All statuses</option>
            {WORKFLOW_FILTER_OPTIONS.map((s) => (
              <option key={s} value={s}>{WORKFLOW_LABELS[s as WorkflowStatus]}</option>
            ))}
          </select>

          <select
            value={dueFilter}
            onChange={(e) => setDueFilter(e.target.value as DueState | "")}
            className="rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-1.5 text-[12px] text-[#191c1e] focus:outline-none focus:border-[#0066cc]"
          >
            <option value="">All due states</option>
            {DUE_STATE_FILTER_OPTIONS.map((s) => (
              <option key={s} value={s}>{s.replace("_", " ")}</option>
            ))}
          </select>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#eceef0]">
                {["Provider", "Form", "Period", "Due Date", "Status", "Due State", "Officer"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-[#737780]">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {submissions.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-[#eceef0]">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-5 py-3">
                        <Skeleton className="h-4 w-full max-w-[120px]" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : !submissions.data?.results.length ? (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-[13px] text-[#737780]">
                    No submissions match the current filters.
                  </td>
                </tr>
              ) : (
                submissions.data.results.map((sub) => (
                  <tr
                    key={sub.id}
                    className="border-b border-[#eceef0] last:border-0 hover:bg-[#f7f9fb] transition-colors cursor-pointer"
                  >
                    <td className="px-5 py-3">
                      <p className="text-[13px] font-medium text-[#191c1e] max-w-[160px] truncate">
                        {sub.provider_name}
                      </p>
                      <p className="text-[11px] text-[#737780]">{sub.provider_category}</p>
                    </td>
                    <td className="px-5 py-3">
                      <p className="text-[12px] font-mono font-medium text-[#002d5b]">{sub.form_code}</p>
                      <p className="text-[11px] text-[#737780] max-w-[140px] truncate">{sub.form_name}</p>
                    </td>
                    <td className="px-5 py-3 text-[12px] text-[#43474f]">{sub.period_name}</td>
                    <td className="px-5 py-3 text-[12px] tabular-nums text-[#43474f]">
                      {sub.due_at ? formatDate(sub.due_at) : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <WorkflowBadge status={sub.workflow_status} />
                    </td>
                    <td className="px-5 py-3">
                      <DueStateBadge state={sub.due_state} />
                    </td>
                    <td className="px-5 py-3 text-[12px] text-[#43474f]">
                      {sub.assigned_officer_name ?? (
                        <span className="text-[#737780]">Unassigned</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination hint */}
        {submissions.data && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-[#eceef0]">
            <p className="text-[12px] text-[#737780]">
              {submissions.data.count} total · showing {submissions.data.results.length}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

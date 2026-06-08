"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission } from "@/lib/types";
import { WORKFLOW_LABELS } from "@/lib/utils";

const STATUS_GROUPS: { label: string; statuses: string[]; color: string }[] = [
  { label: "Action Required", statuses: ["CORRECTION_REQUESTED"], color: "#ffe8e8" },
  { label: "In Progress", statuses: ["NOT_STARTED", "DRAFT", "PENDING_APPROVAL"], color: "#e8f1fb" },
  { label: "Submitted", statuses: ["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED"], color: "#fff3bf" },
  { label: "Completed", statuses: ["APPROVED"], color: "#e5f4eb" },
];

function formatDue(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export default function ProviderDashboardPage() {
  const { data, isLoading } = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["provider-expected-submissions"],
    queryFn: () => api("/expected-submissions/?ordering=period__due_at"),
  });

  const submissions = data?.results ?? [];

  const overdue = submissions.filter((s) => s.due_state === "OVERDUE" && s.workflow_status !== "APPROVED");
  const dueSoon = submissions.filter((s) => s.due_state === "DUE_SOON" && s.workflow_status !== "APPROVED");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[28px] font-semibold text-[#191c1e]">My Submissions</h1>
        <p className="mt-1 text-[14px] text-[#43474f]">
          Track and manage your regulatory data submissions.
        </p>
      </div>

      {/* Alert banners */}
      {!isLoading && overdue.length > 0 && (
        <div className="flex items-start gap-3 rounded-[12px] border border-[#e31937]/30 bg-[#ffe8e8] px-5 py-4">
          <span className="text-[#e31937] text-[18px] mt-0.5" aria-hidden>⚠</span>
          <div>
            <p className="text-[14px] font-semibold text-[#c0112a]">
              {overdue.length} overdue submission{overdue.length > 1 ? "s" : ""}
            </p>
            <p className="text-[13px] text-[#c0112a]/80 mt-0.5">
              Please submit as soon as possible to avoid compliance action.
            </p>
          </div>
        </div>
      )}

      {!isLoading && dueSoon.length > 0 && (
        <div className="flex items-start gap-3 rounded-[12px] border border-[#ffd100]/50 bg-[#fff3bf] px-5 py-4">
          <span className="text-[#7a5c00] text-[18px] mt-0.5" aria-hidden>⏰</span>
          <div>
            <p className="text-[14px] font-semibold text-[#7a5c00]">
              {dueSoon.length} submission{dueSoon.length > 1 ? "s" : ""} due soon
            </p>
            <p className="text-[13px] text-[#7a5c00]/80 mt-0.5">Due within 7 days.</p>
          </div>
        </div>
      )}

      {/* Summary stat row */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[80px] rounded-[12px]" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {STATUS_GROUPS.map((g) => {
            const count = submissions.filter((s) => g.statuses.includes(s.workflow_status)).length;
            return (
              <div
                key={g.label}
                className="rounded-[12px] px-5 py-4"
                style={{ background: g.color }}
              >
                <p className="text-[28px] font-bold text-[#191c1e]">{count}</p>
                <p className="mt-0.5 text-[12px] font-semibold uppercase tracking-wide text-[#43474f]">{g.label}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Submissions table */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <div className="border-b border-[#eceef0] px-6 py-4">
          <h2 className="text-[16px] font-semibold text-[#191c1e]">All Submissions</h2>
        </div>

        {isLoading ? (
          <div className="divide-y divide-[#eceef0]">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4">
                <Skeleton className="h-4 w-1/2 mb-2" />
                <Skeleton className="h-3 w-1/4" />
              </div>
            ))}
          </div>
        ) : submissions.length === 0 ? (
          <div className="px-6 py-12 text-center text-[14px] text-[#737780]">
            No submissions assigned to your account yet.
          </div>
        ) : (
          <div className="divide-y divide-[#eceef0]">
            {submissions.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-[#f7f9fb] transition-colors">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-medium text-[#191c1e]">{s.form_name}</p>
                  <p className="mt-0.5 text-[12px] text-[#737780]">
                    {s.period_name} · Due {formatDue(s.due_at)}
                  </p>
                  {s.workflow_status === "DRAFT" && (
                    <p className="mt-1 text-[11px] text-[#0066cc] font-medium">
                      In progress — continue filling
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <DueStateBadge state={s.due_state} />
                  <WorkflowBadge status={s.workflow_status} />
                  {["NOT_STARTED", "DRAFT", "CORRECTION_REQUESTED"].includes(s.workflow_status) && (
                    <Link
                      href={`/submissions/${s.id}`}
                      className="rounded-[6px] bg-[#001836] px-3 py-1.5 text-[12px] font-semibold text-white transition-colors hover:bg-[#002d5b]"
                    >
                      {s.workflow_status === "NOT_STARTED" ? "Start" : "Continue"}
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

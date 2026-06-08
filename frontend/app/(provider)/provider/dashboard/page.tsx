"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ExpectedSubmission, User } from "@/lib/types";

function formatDue(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day:"numeric", month:"short", year:"numeric" });
}

const STATUS_GROUPS = [
  { label:"Action Required", statuses:["CORRECTION_REQUESTED"],                           color:"#ffe8e8", text:"#c0112a" },
  { label:"In Progress",     statuses:["NOT_STARTED","DRAFT"],                            color:"#e8f1fb", text:"#004999" },
  { label:"Pending Approval",statuses:["PENDING_APPROVAL"],                               color:"#fff3bf", text:"#7a5c00" },
  { label:"Submitted / Done",statuses:["SUBMITTED","UNDER_REVIEW","RESUBMITTED","APPROVED"], color:"#e5f4eb", text:"#1f7a4d" },
];

function actionLabel(status: string): string {
  if (status === "NOT_STARTED") return "Start";
  if (["DRAFT","CORRECTION_REQUESTED"].includes(status)) return "Continue";
  return "View";
}

function actionStyle(status: string): string {
  if (["NOT_STARTED","DRAFT","CORRECTION_REQUESTED"].includes(status))
    return "rounded-[6px] bg-[#001836] px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-[#002d5b]";
  return "rounded-[6px] border border-[#c3c6d0] px-3 py-1.5 text-[12px] font-medium text-[#43474f] hover:bg-[#f2f4f6]";
}

export default function ProviderDashboardPage() {
  const { data: user } = useQuery<User>({ queryKey:["me"], queryFn:()=>api("/auth/me/"), staleTime:5*60*1000 });
  const { data, isLoading } = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["provider-expected-submissions"],
    queryFn: () => api("/expected-submissions/?ordering=period__due_at"),
  });

  const submissions = data?.results ?? [];
  const isApprover = user?.role === "PROVIDER_APPROVER";

  // Data entry sees active work (not yet submitted to NCA)
  // Approver sees their full list on this page (pending approval is on /pending-approval)
  const activeSubmissions = isApprover
    ? submissions
    : submissions.filter(s => !["SUBMITTED","UNDER_REVIEW","APPROVED","REJECTED"].includes(s.workflow_status));

  const overdue = submissions.filter(s => s.due_state === "OVERDUE" && s.workflow_status !== "APPROVED");
  const dueSoon = submissions.filter(s => s.due_state === "DUE_SOON" && !["APPROVED","SUBMITTED"].includes(s.workflow_status));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-[28px] font-semibold text-[#191c1e]">
          {isApprover ? "Submissions Overview" : "My Forms"}
        </h1>
        <p className="mt-1 text-[14px] text-[#43474f]">
          {isApprover
            ? "Review all submissions for your organisation. Go to Pending Approval to officially submit to NCA."
            : "Your assigned regulatory data submissions."}
        </p>
      </div>

      {/* Alert banners */}
      {!isLoading && overdue.length > 0 && (
        <div className="flex items-start gap-3 rounded-[12px] border border-[#e31937]/30 bg-[#ffe8e8] px-5 py-4">
          <span className="text-[#e31937] text-[18px] mt-0.5">⚠</span>
          <div>
            <p className="text-[14px] font-semibold text-[#c0112a]">
              {overdue.length} overdue submission{overdue.length > 1 ? "s" : ""}
            </p>
            <p className="text-[13px] text-[#c0112a]/80 mt-0.5">Submit as soon as possible to avoid compliance action.</p>
          </div>
        </div>
      )}
      {!isLoading && dueSoon.length > 0 && (
        <div className="flex items-start gap-3 rounded-[12px] border border-[#ffd100]/50 bg-[#fff3bf] px-5 py-4">
          <span className="text-[#7a5c00] text-[18px] mt-0.5">⏰</span>
          <div>
            <p className="text-[14px] font-semibold text-[#7a5c00]">
              {dueSoon.length} submission{dueSoon.length > 1 ? "s" : ""} due within 7 days
            </p>
          </div>
        </div>
      )}

      {/* Stat cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[80px] rounded-[12px]" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {STATUS_GROUPS.map(g => {
            const count = submissions.filter(s => g.statuses.includes(s.workflow_status)).length;
            return (
              <div key={g.label} className="rounded-[12px] px-5 py-4" style={{ background: g.color }}>
                <p className="text-[28px] font-bold" style={{ color: g.text }}>{count}</p>
                <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{g.label}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Submissions list */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <div className="border-b border-[#eceef0] px-6 py-4 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[#191c1e]">
            {isApprover ? "All Submissions" : "Active Submissions"}
          </h2>
          {!isApprover && (
            <Link href="/provider/history" className="text-[13px] font-medium text-[#0066cc] hover:underline">
              View history →
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="divide-y divide-[#eceef0]">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4"><Skeleton className="h-4 w-1/2 mb-2" /><Skeleton className="h-3 w-1/4" /></div>
            ))}
          </div>
        ) : activeSubmissions.length === 0 ? (
          <div className="px-6 py-12 text-center text-[14px] text-[#737780]">
            No active submissions. All caught up!
          </div>
        ) : (
          <div className="divide-y divide-[#eceef0]">
            {activeSubmissions.map(s => (
              <div key={s.id} className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-[#f7f9fb] transition-colors">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-medium text-[#191c1e]">{s.form_name}</p>
                  <p className="mt-0.5 text-[12px] text-[#737780]">
                    {s.period_name} · Due {formatDue(s.due_at)}
                  </p>
                  {s.workflow_status === "PENDING_APPROVAL" && !isApprover && (
                    <p className="mt-1 text-[11px] text-[#7a5c00] font-medium">Awaiting approver review</p>
                  )}
                  {s.workflow_status === "CORRECTION_REQUESTED" && (
                    <p className="mt-1 text-[11px] text-[#c0112a] font-medium">NCA has requested corrections</p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <DueStateBadge state={s.due_state} />
                  <WorkflowBadge status={s.workflow_status} />
                  {/* Data entry: can't touch PENDING_APPROVAL unless correction requested */}
                  {!isApprover && s.workflow_status === "PENDING_APPROVAL" ? (
                    <Link href={`/provider/submissions/${s.id}`} className={actionStyle("view")}>View</Link>
                  ) : (
                    <Link href={`/provider/submissions/${s.id}`} className={actionStyle(s.workflow_status)}>
                      {actionLabel(s.workflow_status)}
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

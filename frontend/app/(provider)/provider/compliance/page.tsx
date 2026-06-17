"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDateTime } from "@/lib/utils";
import { ShieldAlert, CheckCircle2, AlertTriangle, Mail, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { PaginatedResponse } from "@/lib/types";

interface ComplianceFlag {
  id: number;
  expected_submission: number;
  provider_name: string;
  form_code: string;
  period_name: string;
  flag_type: string;
  description: string;
  missing_field_count: number;
  completion_percentage: number;
  status: "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "RESOLVED";
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

const FLAG_TYPE_LABELS: Record<string, string> = {
  MISSING_DATA: "Missing Data",
  OVERDUE: "Overdue",
  INCOMPLETE: "Incomplete",
  CORRECTION: "Correction",
};

const FLAG_STATUS_STYLES: Record<string, string> = {
  OPEN: "bg-[#ffe8e8] text-[#c0112a]",
  ACKNOWLEDGED: "bg-[#fff3bf] text-[#7a5c00]",
  IN_PROGRESS: "bg-[#e8f1fb] text-[#004999]",
  RESOLVED: "bg-[#e5f4eb] text-[#1f7a4d]",
};

export default function ProviderCompliancePage() {
  const flagsQ = useQuery({
    queryKey: ["my-compliance-flags"],
    queryFn: () => api.get<PaginatedResponse<ComplianceFlag>>("/compliance/my-flags/"),
  });

  const flags = flagsQ.data?.results ?? [];
  const openCount = flags.filter((f) => f.status === "OPEN" || f.status === "ACKNOWLEDGED").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[22px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>
          Compliance Notices
        </h1>
        <p className="text-[13px] text-[#737780] mt-0.5">
          Review outstanding data issues flagged by NCA. Complete missing fields to resolve flags.
        </p>
      </div>

      {/* Summary banner */}
      {openCount > 0 && (
        <div className="flex items-start gap-3 rounded-[12px] border border-[#E31937]/20 bg-[#ffe8e8] px-5 py-4">
          <AlertTriangle size={16} className="text-[#E31937] shrink-0 mt-0.5" />
          <div>
            <p className="text-[13px] font-semibold text-[#c0112a]">
              {openCount} active compliance issue{openCount !== 1 ? "s" : ""} require your attention
            </p>
            <p className="text-[12px] text-[#c0112a]/80 mt-0.5">
              Review each flag below and update your submissions with the missing information. Contact{" "}
              <a href="mailto:compliance@nca.org.gh" className="underline font-medium">compliance@nca.org.gh</a>
              {" "}if you need assistance.
            </p>
          </div>
        </div>
      )}

      {/* Flags list */}
      <div className="rounded-[16px] bg-white border border-[#e6e8ea]"
        style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>
        <div className="flex items-center gap-2 px-5 py-4 border-b border-[#eceef0]">
          <ShieldAlert size={15} className="text-[#E31937]" />
          <p className="text-[13px] font-semibold text-[#191c1e]">My Compliance Flags</p>
          {flagsQ.data?.count != null && (
            <span className="rounded-full bg-[#f2f4f6] px-2 py-0.5 text-[11px] font-bold text-[#43474f]">
              {flagsQ.data.count}
            </span>
          )}
        </div>

        {flagsQ.isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
          </div>
        ) : flags.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <CheckCircle2 size={28} className="mx-auto text-[#1f7a4d] mb-3" />
            <p className="text-[14px] font-semibold text-[#191c1e]">All clear</p>
            <p className="text-[12px] text-[#737780] mt-1">You have no outstanding compliance issues.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#f2f4f6]">
            {flags.map((flag) => (
              <div key={flag.id} className="px-5 py-4 flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${FLAG_STATUS_STYLES[flag.status]}`}>
                      {flag.status}
                    </span>
                    <span className="rounded-full bg-[#f2f4f6] px-2 py-0.5 text-[10px] font-semibold text-[#43474f] uppercase">
                      {FLAG_TYPE_LABELS[flag.flag_type] ?? flag.flag_type}
                    </span>
                  </div>
                  <p className="text-[13px] font-medium text-[#191c1e]">
                    <span className="font-mono">{flag.form_code}</span> · {flag.period_name}
                  </p>
                  <p className="text-[12px] text-[#43474f] mt-0.5">{flag.description}</p>

                  {/* Completion bar */}
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1.5 rounded-full bg-[#eceef0] overflow-hidden" style={{ width: 140 }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${flag.completion_percentage}%`,
                          background: flag.completion_percentage >= 80 ? "#1f7a4d"
                            : flag.completion_percentage >= 40 ? "#ffd100"
                            : "#E31937",
                        }}
                      />
                    </div>
                    <span className="text-[11px] font-semibold text-[#43474f]">{flag.completion_percentage}%</span>
                    <span className="text-[10px] text-[#737780]">· {flag.missing_field_count} fields missing</span>
                  </div>

                  <p className="text-[10px] text-[#737780] mt-1">Flagged {formatDateTime(flag.created_at)}</p>
                </div>

                <div className="flex items-center gap-2 shrink-0 mt-1">
                  <a href="mailto:compliance@nca.org.gh"
                    className="flex items-center gap-1 rounded-[6px] border border-[#c3c6d0] px-3 py-1.5 text-[11px] font-medium text-[#43474f] hover:bg-[#f2f4f6]">
                    <Mail size={11} /> Email NCA
                  </a>
                  <Link href={`/provider/submissions/${flag.expected_submission}`}
                    className="flex items-center gap-1 rounded-[6px] bg-[#002d5b] px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-[#001836]">
                    Update submission <ChevronRight size={11} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <p className="text-[11px] text-[#737780] text-center">
        Questions about a compliance notice? Contact{" "}
        <a href="mailto:compliance@nca.org.gh" className="text-[#0066cc] hover:underline font-medium">
          compliance@nca.org.gh
        </a>
      </p>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";

type Readiness = {
  ready: boolean;
  blockers: { code: string; detail: string }[];
  approved_policy_count: number;
  required_policy_count: number;
  active_legal_holds: number;
  last_backup: string | null;
  last_restore: string | null;
};

type TaskRun = { id: number; task_name: string; status: string; completed_at: string | null; processed_count: number };
type Page<T> = { results: T[] };

export default function GovernancePage() {
  const readiness = useQuery<Readiness>({ queryKey: ["governance-readiness"], queryFn: () => api.get("/governance/readiness/") });
  const tasks = useQuery<Page<TaskRun>>({ queryKey: ["governance-task-runs"], queryFn: () => api.get("/governance/task-runs/") });

  if (readiness.isLoading) return <Skeleton className="h-64 w-full" />;
  const state = readiness.data;
  return <div className="max-w-[1100px] space-y-6">
    <div>
      <h1 className="text-[22px] font-semibold text-[#191c1e]">Production Readiness</h1>
      <p className="mt-1 text-[13px] text-[#737780]">Read-only launch gates. Missing external approvals remain blockers and do not activate production controls.</p>
    </div>

    <div className={`rounded-[14px] border p-5 ${state?.ready ? "border-[#1f7a4d] bg-[#eef8f2]" : "border-[#e31937]/30 bg-[#fff8f8]"}`}>
      <p className="text-[16px] font-semibold text-[#191c1e]">{state?.ready ? "All launch gates passed" : `${state?.blockers.length ?? 0} launch blockers`}</p>
      <div className="mt-3 grid grid-cols-2 gap-3 text-[12px] md:grid-cols-4">
        <span>Policies: {state?.approved_policy_count}/{state?.required_policy_count}</span>
        <span>Legal holds: {state?.active_legal_holds}</span>
        <span>Last backup: {state?.last_backup ? new Date(state.last_backup).toLocaleString() : "None"}</span>
        <span>Last restore: {state?.last_restore ? new Date(state.last_restore).toLocaleString() : "None"}</span>
      </div>
    </div>

    <div className="rounded-[14px] border border-[#e6e8ea] bg-white">
      <div className="border-b border-[#eceef0] px-5 py-4 text-[13px] font-semibold">Outstanding gates</div>
      <div className="divide-y divide-[#f2f4f6]">
        {(state?.blockers ?? []).map(blocker => <div key={blocker.code} className="px-5 py-3">
          <p className="text-[11px] font-bold text-[#c0112a]">{blocker.code}</p>
          <p className="mt-0.5 text-[12px] text-[#43474f]">{blocker.detail}</p>
        </div>)}
      </div>
    </div>

    <div className="rounded-[14px] border border-[#e6e8ea] bg-white">
      <div className="border-b border-[#eceef0] px-5 py-4 text-[13px] font-semibold">Operational task history</div>
      <div className="divide-y divide-[#f2f4f6]">
        {(tasks.data?.results ?? []).map(run => <div key={run.id} className="flex items-center gap-3 px-5 py-3 text-[12px]">
          <span className="flex-1 font-medium">{run.task_name}</span><span>{run.processed_count} processed</span>
          <span className={run.status === "SUCCEEDED" ? "text-[#1f7a4d]" : "text-[#c0112a]"}>{run.status}</span>
          <span className="text-[#737780]">{run.completed_at ? new Date(run.completed_at).toLocaleString() : "Running"}</span>
        </div>)}
      </div>
    </div>
  </div>;
}

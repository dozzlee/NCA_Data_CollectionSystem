import { cn } from "@/lib/utils";
import type { WorkflowStatus, DueState } from "@/lib/types";
import { getWorkflowStatusColor, getDueStateColor, WORKFLOW_LABELS, DUE_STATE_LABELS } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "critical" | "muted";
}

export function Badge({ children, className, variant = "default" }: BadgeProps) {
  const variants = {
    default: "bg-[#eceef0] text-[#43474f]",
    success: "bg-[#e5f4eb] text-[#1f7a4d]",
    warning: "bg-[#fff3bf] text-[#7a5c00]",
    critical: "bg-[#ffe8e8] text-[#E31937]",
    muted: "bg-[#f2f4f6] text-[#737780]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold leading-4",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

export function WorkflowBadge({ status }: { status: WorkflowStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold leading-4",
        getWorkflowStatusColor(status)
      )}
    >
      {WORKFLOW_LABELS[status]}
    </span>
  );
}

export function DueStateBadge({ state }: { state: DueState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold leading-4",
        getDueStateColor(state)
      )}
    >
      {DUE_STATE_LABELS[state]}
    </span>
  );
}

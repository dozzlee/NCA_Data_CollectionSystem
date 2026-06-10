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
    default:  "bg-[#eceef0] text-[#43474f]",
    success:  "bg-[#e5f4eb] text-[#1f7a4d]",
    warning:  "bg-[#fff3bf] text-[#7a5c00]",
    critical: "bg-[#ffe8e8] text-[#E31937]",
    muted:    "bg-[#f2f4f6] text-[#737780]",
  };
  return (
    <span className={cn(
      "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold leading-4",
      variants[variant], className
    )}>
      {children}
    </span>
  );
}

export function WorkflowBadge({ status }: { status: WorkflowStatus }) {
  return (
    <span className={cn(
      "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold leading-4",
      getWorkflowStatusColor(status)
    )}>
      {WORKFLOW_LABELS[status]}
    </span>
  );
}

/** Prominent due-state badge — urgent states show an icon and bolder style */
export function DueStateBadge({ state }: { state: DueState }) {
  const urgent = state === "OVERDUE" || state === "DUE_TODAY";
  const soon   = state === "DUE_SOON";

  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold leading-4",
      getDueStateColor(state),
      urgent && "ring-1 ring-current",
    )}>
      {urgent && <span className="text-[10px] leading-none">●</span>}
      {soon   && <span className="text-[10px] leading-none">◐</span>}
      {DUE_STATE_LABELS[state]}
    </span>
  );
}

/** Inline due urgency indicator for table rows — more compact */
export function DueUrgencyBar({ state, workflowStatus }: { state: DueState; workflowStatus?: WorkflowStatus }) {
  if (workflowStatus === "APPROVED" || state === "CLOSED" || state === "NOT_OPEN" || state === "OPEN") return null;

  const config = {
    OVERDUE:   { label: "Overdue",   color: "#e31937", bg: "#ffe8e8" },
    DUE_TODAY: { label: "Due Today", color: "#f97316", bg: "#fde8c8" },
    DUE_SOON:  { label: "Due Soon",  color: "#b45309", bg: "#fff3bf" },
  }[state];

  if (!config) return null;

  return (
    <span className="inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
      style={{ background: config.bg, color: config.color }}>
      ⚑ {config.label}
    </span>
  );
}

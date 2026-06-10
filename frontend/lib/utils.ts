import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { WorkflowStatus, DueState } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const WORKFLOW_LABELS: Record<WorkflowStatus, string> = {
  NOT_STARTED: "Not Started",
  DRAFT: "Draft",
  PENDING_APPROVAL: "Pending Approval",
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under Review",
  CORRECTION_REQUESTED: "Correction Requested",
  RESUBMITTED: "Resubmitted",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  ARCHIVED: "Archived",
};

export const DUE_STATE_LABELS: Record<DueState, string> = {
  NOT_OPEN: "Not Open",
  OPEN: "Open",
  DUE_SOON: "Due Soon",
  DUE_TODAY: "Due Today",
  OVERDUE: "Overdue",
  CLOSED: "Closed",
};

export const PROVIDER_CATEGORY_LABELS: Record<string, string> = {
  MNO: "MNO",
  ISP: "ISP",
  PAY_TV: "Pay TV",
  TOWER_OPERATOR: "Tower Operator",
  TOWER_MAIN: "Tower Main",
  DOMESTIC_FIBRE: "Domestic Fibre",
  SUBMARINE_FIBRE: "Submarine Fibre",
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getWorkflowStatusColor(status: WorkflowStatus): string {
  const map: Partial<Record<WorkflowStatus, string>> = {
    NOT_STARTED:          "bg-[#f2f4f6] text-[#737780]",
    DRAFT:                "bg-[#e8f1fb] text-[#004999]",
    PENDING_APPROVAL:     "bg-[#fff3bf] text-[#7a5c00]",
    SUBMITTED:            "bg-[#e8f1fb] text-[#0066cc]",
    UNDER_REVIEW:         "bg-[#ede9ff] text-[#5b21b6]",
    CORRECTION_REQUESTED: "bg-[#ffe8e8] text-[#c0112a]",
    RESUBMITTED:          "bg-[#e0f5f1] text-[#0d6657]",
    APPROVED:             "bg-[#e5f4eb] text-[#1f7a4d]",
    REJECTED:             "bg-[#ffe8e8] text-[#c0112a]",
    ARCHIVED:             "bg-[#f2f4f6] text-[#737780]",
  };
  return map[status] ?? "bg-[#f2f4f6] text-[#737780]";
}

export function getDueStateColor(state: DueState): string {
  const map: Partial<Record<DueState, string>> = {
    NOT_OPEN:  "bg-[#f2f4f6] text-[#737780]",
    OPEN:      "bg-[#e8f1fb] text-[#004999]",
    DUE_SOON:  "bg-[#fff3bf] text-[#7a5c00]",
    DUE_TODAY: "bg-[#fde8c8] text-[#92400e]",
    OVERDUE:   "bg-[#ffe8e8] text-[#c0112a]",
    CLOSED:    "bg-[#e5f4eb] text-[#1f7a4d]",
  };
  return map[state] ?? "bg-[#f2f4f6] text-[#737780]";
}

/** Row background color driven by due urgency — use on <tr> or <div> */
export function getDueStateRowBg(state: DueState, workflowStatus?: WorkflowStatus): string {
  if (workflowStatus === "APPROVED") return "";
  switch (state) {
    case "OVERDUE":   return "bg-[#fff8f8] border-l-2 border-l-[#e31937]";
    case "DUE_TODAY": return "bg-[#fffcf5] border-l-2 border-l-[#f97316]";
    case "DUE_SOON":  return "bg-[#fffef0] border-l-2 border-l-[#ffd100]";
    default:          return "";
  }
}

// Chart colors aligned with design system
export const CHART_COLORS = {
  primary: "#0066cc",
  success: "#1f7a4d",
  warning: "#ffd100",
  danger: "#e31937",
  navy: "#002d5b",
  muted: "#c3c6d0",
};

export const STATUS_CHART_COLORS: Partial<Record<WorkflowStatus, string>> = {
  NOT_STARTED: "#c3c6d0",
  DRAFT: "#93c5fd",
  PENDING_APPROVAL: "#fde68a",
  SUBMITTED: "#818cf8",
  UNDER_REVIEW: "#c084fc",
  CORRECTION_REQUESTED: "#fb923c",
  RESUBMITTED: "#2dd4bf",
  APPROVED: "#1f7a4d",
  REJECTED: "#e31937",
  ARCHIVED: "#9ca3af",
};

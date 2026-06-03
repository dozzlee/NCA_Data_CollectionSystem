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
    NOT_STARTED: "bg-surface-container text-on-surface-variant",
    DRAFT: "bg-blue-50 text-blue-700",
    PENDING_APPROVAL: "bg-yellow-50 text-yellow-700",
    SUBMITTED: "bg-indigo-50 text-indigo-700",
    UNDER_REVIEW: "bg-purple-50 text-purple-700",
    CORRECTION_REQUESTED: "bg-orange-50 text-orange-700",
    RESUBMITTED: "bg-teal-50 text-teal-700",
    APPROVED: "bg-success-soft text-success",
    REJECTED: "bg-critical-soft text-nca-red",
    ARCHIVED: "bg-gray-100 text-gray-500",
  };
  return map[status] ?? "bg-gray-100 text-gray-500";
}

export function getDueStateColor(state: DueState): string {
  const map: Partial<Record<DueState, string>> = {
    NOT_OPEN: "bg-gray-100 text-gray-500",
    OPEN: "bg-blue-50 text-blue-700",
    DUE_SOON: "bg-warning-soft text-yellow-800",
    DUE_TODAY: "bg-orange-50 text-orange-700",
    OVERDUE: "bg-critical-soft text-nca-red",
    CLOSED: "bg-success-soft text-success",
  };
  return map[state] ?? "bg-gray-100 text-gray-500";
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

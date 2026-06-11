// ─── Auth ────────────────────────────────────────────────────────────────────

export type UserRole =
  | "NCA_ADMIN"
  | "NCA_OFFICER"
  | "PROVIDER_ADMIN"
  | "PROVIDER_DATA_ENTRY"
  | "PROVIDER_APPROVER";

export interface Organization {
  id: number;
  name: string;
  org_type: "NCA" | "PROVIDER";
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  organization: Organization | null;
  is_active: boolean;
  mfa_enabled: boolean;
  created_at: string;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

// ─── Provider ────────────────────────────────────────────────────────────────

export type ProviderCategory =
  | "MNO"
  | "ISP"
  | "PAY_TV"
  | "TOWER_OPERATOR"
  | "TOWER_MAIN"
  | "DOMESTIC_FIBRE"
  | "SUBMARINE_FIBRE";

export type ProviderStatus = "ACTIVE" | "INACTIVE" | "SUSPENDED" | "ARCHIVED";

export interface ProviderProfile {
  id: number;
  provider_id: string;
  organization: number | null;
  registered_name: string;
  trade_name: string;
  category: ProviderCategory;
  licence_type: string;
  licence_number: string;
  licence_issue_date: string | null;
  licence_expiry_date: string | null;
  physical_address: string;
  digital_address: string;
  postal_address: string;
  website: string;
  primary_email: string;
  primary_phone: string;
  status: ProviderStatus;
  contact_count?: number;
  expected_count?: number;
  overdue_count?: number;
  open_count?: number;
  created_at?: string;
  updated_at?: string;
}

// ─── Forms Engine ────────────────────────────────────────────────────────────

export type FormCode =
  | "MNO-MONTHLY"
  | "DC-TB02"
  | "DC-ISP06"
  | "DC-ITC04"
  | "TOWER-MAIN-ANNUAL"
  | "DC-DBS05"
  | "DC-SUB03";

export type Frequency = "MONTHLY" | "SEMI_ANNUAL" | "ANNUAL";

export type FieldType =
  | "text" | "number" | "currency" | "percentage" | "date"
  | "boolean" | "select" | "multiselect" | "textarea"
  | "coordinate" | "formula" | "declaration";

export interface FormTemplate {
  id: number;
  form_code: FormCode;
  name: string;
  provider_category: ProviderCategory;
  frequency: Frequency;
  version: string;
  status: "DRAFT" | "ACTIVE" | "ARCHIVED";
  kmz_required: boolean;
  excel_backup_enabled: boolean;
  instructions?: string;
  sections?: FormSection[];
}

export interface FormSection {
  id: number;
  section_code: string;
  title: string;
  instructions: string;
  sort_order: number;
  kmz_upload_required: boolean;
  fields: FormField[];
  grids: FormGrid[];
}

export interface FormField {
  id: number;
  field_code: string;
  label: string;
  field_type: FieldType;
  unit: string;
  is_required: boolean;
  help_text: string;
  formula: string;
  conditional_on_field: number | null;
  conditional_on_value: string;
  sort_order: number;
  options?: SelectOption[];
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface FormGrid {
  id: number;
  grid_code: string;
  title: string;
  row_mode: "FIXED" | "REPEATABLE";
  sort_order: number;
  instructions?: string;
  columns: GridColumn[];
  fixed_rows?: GridRow[];
}

export interface GridColumn {
  id: number;
  column_code: string;
  label: string;
  field_type: FieldType;
  unit: string;
  is_required: boolean;
}

export interface GridRow {
  id: number;
  row_label: string;
  sort_order: number;
}

// ─── Submissions ─────────────────────────────────────────────────────────────

export type WorkflowStatus =
  | "NOT_STARTED" | "DRAFT" | "PENDING_APPROVAL" | "SUBMITTED"
  | "UNDER_REVIEW" | "CORRECTION_REQUESTED" | "RESUBMITTED"
  | "APPROVED" | "REJECTED" | "ARCHIVED";

export type DueState =
  | "NOT_OPEN" | "OPEN" | "DUE_SOON" | "DUE_TODAY" | "OVERDUE" | "CLOSED";

export type FieldStatus =
  | "MISSING" | "PROVIDED" | "OPTIONAL_NOT_PROVIDED" | "NOT_APPLICABLE"
  | "NOT_AVAILABLE" | "NOT_REQUIRED" | "PENDING_CLARIFICATION"
  | "WAITING_CORRECTION" | "SYSTEM_CALCULATED";

export interface ReportingPeriod {
  id: number;
  name: string;
  frequency: Frequency;
  year: number;
  month: number | null;
  opens_at: string;
  due_at: string;
  status: "DRAFT" | "ACTIVE" | "CLOSED";
  applicable_form_templates?: number[];
  assigned_providers?: number[];
  created_at?: string;
  created_by?: string;
  created_by_name?: string | null;
  expected_count?: number;
  assigned_provider_count?: number;
  form_template_count?: number;
}

export interface ExpectedSubmission {
  id: number;
  provider: number;
  provider_name: string;
  provider_category: ProviderCategory;
  form_template: number;
  form_code: FormCode;
  form_name: string;
  period: number;
  period_name: string;
  due_at: string;
  due_at_override: string | null;
  workflow_status: WorkflowStatus;
  due_state: DueState;
  assigned_officer: number | null;
  assigned_officer_name: string | null;
  created_at: string;
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardSummary {
  total_expected: number;
  not_started: number;
  draft: number;
  pending_approval: number;
  submitted: number;
  under_review: number;
  correction_requested: number;
  resubmitted: number;
  approved: number;
  rejected: number;
  overdue: number;
  due_soon: number;
  completion_pct: number;
}

export interface StatusDonutItem {
  workflow_status: WorkflowStatus;
  count: number;
}

export interface CategoryCompletionItem {
  category: ProviderCategory;
  completion_pct: number;
  total: number;
  approved: number;
}

export interface OverdueByFormItem {
  form_template__form_code: FormCode;
  form_template__name: string;
  count: number;
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

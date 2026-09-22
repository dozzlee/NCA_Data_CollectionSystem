// ─── Auth ────────────────────────────────────────────────────────────────────

export type UserRole =
  | "NCA_ADMIN"           // System Administrator
  | "NCA_OFFICER"         // NCA Officer
  | "NCA_VIEWER"          // Governed NCA data requester
  | "PROVIDER_DATA_ENTRY" // Provider Data Entry User
  | "PROVIDER_APPROVER";  // Provider Approver

export interface Organization {
  id: number;
  name: string;
  org_type: "NCA" | "PROVIDER";
}

export interface NCADivision {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  organization: Organization | null;
  division: NCADivision | null;
  grade: string;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  capabilities: {
    can_view_nca_operations: boolean;
    can_review_submissions: boolean;
    can_manage_compliance: boolean;
    can_manage_periods: boolean;
    can_manage_forms: boolean;
    can_manage_users: boolean;
    can_export: boolean;
    can_request_data: boolean;
    can_manage_data_requests: boolean;
  };
}

export type DataRequestStatus =
  | "SUBMITTED" | "UNDER_REVIEW" | "CHANGES_REQUESTED" | "APPROVED"
  | "PREPARING" | "READY" | "GENERATION_FAILED" | "REJECTED"
  | "WITHDRAWN" | "EXPIRED";

export interface DataRequestScope {
  form_template_ids: number[];
  period_ids: number[];
  all_fields: boolean;
  field_ids: number[];
  grid_column_ids: number[];
  provider_scope: "ALL" | "SECTOR" | "CATEGORY" | "SELECTED";
  sector: string;
  provider_category: string;
  provider_ids: number[];
}

export interface DataRequestEvent {
  id: number;
  actor_name: string;
  actor_email: string;
  event_type: string;
  from_status: string;
  to_status: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DataRequestArtifact {
  filename: string;
  mime_type: string;
  file_size: number;
  row_count: number;
  sha256: string;
  generated_at: string;
  expires_at: string;
  is_expired: boolean;
}

export interface DataRequestItem {
  id: string;
  requester: string;
  requester_name: string;
  requester_email: string;
  requesting_division: string;
  requester_grade_snapshot: string;
  title: string;
  purpose: string;
  requested_format: "CSV" | "XLSX" | "PDF";
  scope: DataRequestScope;
  dataset_names: string[];
  period_names: string[];
  provider_names: string[];
  status: DataRequestStatus;
  reviewer_name: string | null;
  expected_delivery_at: string | null;
  decision_note: string;
  submitted_at: string;
  updated_at: string;
  approved_at: string | null;
  completed_at: string | null;
  projected_row_count: number | null;
  events: DataRequestEvent[];
  artifact?: DataRequestArtifact;
}

export interface CatalogField {
  id: number; code: string; label: string; type: string; unit: string;
  description: string; required: boolean;
}
export interface CatalogGrid {
  id: number; code: string; title: string; description: string; row_mode: string;
  columns: CatalogField[];
}
export interface CatalogForm {
  id: number; code: string; name: string; description: string; sector: string;
  provider_category: string; frequency: string; version: string;
  available_period_ids: number[];
  applicable_provider_ids: number[];
  applicable_provider_ids_by_period: Record<string, number[]>;
  sections: Array<{ id: number; code: string; title: string; description: string; fields: CatalogField[]; grids: CatalogGrid[] }>;
}
export interface DataCatalog {
  forms: CatalogForm[];
  periods: Array<{ id: number; name: string; frequency: string; year: number; month: number | null }>;
  providers: Array<{ id: number; provider_id: string; name: string; trade_name: string; sector: string; category: string }>;
  sectors: string[];
  provider_categories: string[];
  frequencies: string[];
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
export type Sector = "TELECOM" | "BROADCASTING";

export interface ProviderProfile {
  id: number;
  provider_id: string;
  provider_code: string;
  organization_id: number | null;
  registered_name: string;
  trade_name: string;
  sector: Sector;
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
}

// ─── Forms Engine ────────────────────────────────────────────────────────────

export type FormCode = string;

export type Frequency = "MONTHLY" | "QUARTERLY" | "SEMI_ANNUAL" | "ANNUAL";

export type FieldType =
  | "text" | "number" | "currency" | "percentage" | "date"
  | "boolean" | "select" | "multiselect" | "textarea"
  | "coordinate" | "formula" | "declaration" | "attachment";

export interface FormTemplate {
  id: number;
  family: number | null;
  form_code: FormCode;
  name: string;
  sector: Sector;
  provider_category: ProviderCategory;
  frequency: Frequency;
  version: string;
  effective_from: string;
  status: "DRAFT" | "ACTIVE" | "ARCHIVED";
  kmz_required: boolean;
  excel_backup_enabled: boolean;
  mapping_complete: boolean;
  mapping_basis: "LEGACY" | "PRD_SECTION_11" | "SOURCE_FORM" | "CUSTOM";
  approval_status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED";
  source_reference: string;
  source_sha256: string;
  approved_at: string | null;
  published_at: string | null;
}

export interface FormGapAssessment {
  id: number;
  requirement: number;
  requirement_key: string;
  requirement_label: string;
  requirement_type: "SECTION" | "FIELD" | "GRID" | "GRID_COLUMN" | "FIXED_ROWS" | "OPTION" | "UNIT" | "VALIDATION" | "CONDITIONAL" | "FORMULA" | "DECLARATION" | "KMZ" | "SOURCE_DECISION" | "SPECIAL_HANDLING";
  severity: "BLOCKER" | "HIGH" | "MEDIUM" | "LOW";
  status: "MISSING" | "PARTIAL" | "MATCHED" | "NOT_APPLICABLE";
  evidence: string;
  resolution_note: string;
  owner_name: string | null;
  assessed_at: string | null;
}

export interface ProviderFormAssignment {
  id: number;
  provider: number;
  provider_name: string;
  provider_public_id: string;
  form_family: number;
  form_code: FormCode;
  form_name: string;
  obligation: "REQUIRED" | "OPTIONAL" | "EXEMPT";
  effective_from: string;
  effective_to: string | null;
  source_reference: string;
}

export interface FormSection {
  id: number;
  section_code: string;
  title: string;
  instructions: string;
  sort_order: number;
  kmz_upload_required: boolean;
  kmz_requirements: KMZRequirement[];
  headings: FormHeading[];
  fields: FormField[];
  grids: FormGrid[];
}

export interface FormHeading {
  id: number;
  heading_code: string;
  title: string;
  level: 1 | 2 | 3;
  sort_order: number;
  source_row: number;
}

export interface KMZRequirement {
  id: number;
  category: string;
  description: string;
  is_required: boolean;
  max_file_size_mb: number;
}

export interface FormField {
  id: number;
  heading: number | null;
  heading_code: string;
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
  source_sheet?: string;
  source_row?: number | null;
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
  instructions?: string;
  row_mode: "FIXED" | "REPEATABLE";
  min_rows: number;
  sort_order: number;
  source_sheet?: string;
  source_row?: number | null;
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
  source_sheet?: string;
  source_row?: number | null;
}

export interface GridRow {
  id: number;
  row_label: string;
  sort_order: number;
  source_sheet?: string;
  source_rows?: number[];
}

// ─── Submissions ─────────────────────────────────────────────────────────────

export type WorkflowStatus =
  | "NOT_STARTED" | "DRAFT" | "PENDING_APPROVAL" | "PROVIDER_CHANGES_REQUESTED" | "PROVIDER_RESUBMITTED" | "SUBMITTED"
  | "UNDER_REVIEW" | "CORRECTION_REQUESTED" | "RESUBMITTED"
  | "APPROVED" | "REJECTED" | "ARCHIVED";

export type ProviderFormStatus = "IN_PROGRESS" | "AWAITING_APPROVAL" | "CORRECTIONS_REQUIRED" | "CLOSED";
export type RegulatoryStatus = "DRAFT" | "SUBMITTED" | "UNDER_REVIEW" | "RETURNED_FOR_CORRECTION" | "APPROVED" | "REJECTED";

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
  quarter: number | null;
  opens_at: string;
  due_at: string;
  effective_due_at: string;
  status: "DRAFT" | "ACTIVE" | "CLOSED";
}

export interface ExpectedSubmission {
  id: number;
  provider: number;
  provider_name: string;
  provider_sector: Sector;
  provider_category: ProviderCategory;
  form_template: number | null;
  form_code: FormCode;
  form_name: string;
  form_sector: Sector;
  form_version: string;
  form_created_at: string | null;
  period: number;
  period_name: string;
  due_at: string;
  effective_due_at: string;
  due_at_override: string | null;
  workflow_status: WorkflowStatus;
  provider_status: ProviderFormStatus;
  form_reference: string;
  due_state: DueState;
  assigned_officer: number | null;
  assigned_officer_name: string | null;
  latest_submission_id: number | null;
  submission_reference: string | null;
  latest_submission_version: number | null;
  completion_pct: number;
  last_edited_by: string | null;
  last_edited_by_name: string | null;
  last_edited_at: string | null;
  submitted_at: string | null;
  correction_count: number;
  open_correction_count: number;
  open_compliance_flag_count: number;
  compliance_flag_types: string[];
  receipt_available: boolean;
  receipt_reference: string | null;
  permitted_actions: string[];
  assignment_source: { type: "MANUAL" | "RECURRING" | "LEGACY"; id: number | null };
  ownership_label: "Shared Data Entry queue";
  data_entry_team: Array<{ id: string; name: string; email: string }>;
  last_data_entry_editor: { id: string; name: string; email: string; edited_at: string } | null;
  sent_at: string;
  latest_message: { subject: string; preview: string; body: string; event_type: string; created_at: string } | null;
  latest_action: { code: string; label: string; from_status: string; to_status: string } | null;
  latest_action_at: string | null;
  latest_communication_at: string | null;
  penalty_amount_ghs: string;
  penalty_reference: string;
  penalty_note: string;
  penalty_updated_by: string | null;
  penalty_updated_at: string | null;
  created_at: string;
}

export interface FormalSubmission {
  id: number;
  expected: number;
  submission_reference: string;
  form_reference: string;
  version: number;
  provider_name: string;
  form_code: FormCode;
  form_name: string;
  form_version: string;
  period_name: string;
  submitted_at: string | null;
  regulatory_status: RegulatoryStatus;
  provider_display_status?: RegulatoryStatus | "FLAGGED";
  workflow_status: RegulatoryStatus;
  responsible_approver: string | null;
  receipt_available: boolean;
  receipt_reference: string | null;
  latest_message: { subject: string; preview: string; body: string; event_type: string; created_at: string } | null;
  latest_action: { code: string; label: string; from_status: string; to_status: string } | null;
  latest_action_at: string | null;
  latest_communication_at: string | null;
  form_task_id?: number;
  latest_submission_id?: number;
  formal_versions?: Array<{id:number;version:number;submission_reference:string;regulatory_status:RegulatoryStatus;submitted_at:string|null}>;
}

export type ExcelImportMatchStatus = "MATCHED" | "UNMATCHED" | "AMBIGUOUS" | "DUPLICATE" | "INVALID" | "SKIPPED";

export interface SubmissionExcelImportMatch {
  id: number;
  source_locator: string;
  source_sheet: string;
  source_row: number;
  indicator_code: string;
  indicator_name: string;
  definition: string;
  raw_value: string | number | boolean | null;
  converted_value: string;
  status: ExcelImportMatchStatus;
  score: string;
  evidence: Record<string, unknown>;
  target_type: "FIELD" | "GRID_CELL" | "";
  target_key: string;
  field: number | null;
  grid: number | null;
  grid_row_id: string;
  grid_column: number | null;
  target_label: string;
  current_value: string;
  will_overwrite: boolean;
  user_confirmed: boolean;
}

export interface SubmissionExcelImport {
  id: number;
  submission: number;
  status: "SCANNING" | "PARSING" | "READY" | "IMPORTING" | "IMPORTED" | "FAILED";
  parser_version: string;
  matcher_version: string;
  layout_fingerprint: string;
  source_revision: number;
  summary: {
    detected?: number;
    counts?: Partial<Record<ExcelImportMatchStatus, number>>;
    missing_required?: number;
    warnings?: Array<{sheet:string;row?:number;message:string}>;
    missing_targets?: Array<{target_key:string;label:string;required:boolean}>;
    unresolved_populated?: Array<{source_locator:string;indicator:string;status:ExcelImportMatchStatus}>;
  };
  errors: Array<{code:string;message:string}>;
  imported_manifest: {
    match_ids?: number[];
    changed_targets?: number;
    unresolved_populated?: Array<{id:number;source_locator:string;indicator_name:string;status:ExcelImportMatchStatus}>;
    skipped_populated?: Array<{id:number;source_locator:string;indicator_name:string}>;
    reconciled?: boolean;
  };
  file_name: string;
  file_size: number;
  sha256: string;
  scan_status: string;
  created_at: string;
  updated_at: string;
    resulting_revision: number | null;
    matches: SubmissionExcelImportMatch[];
    matches_meta: { count:number; page:number; page_size:number; pages:number };
  }

export interface SubmissionCommunication {
  id: number;
  event_type: string;
  channel: "SYSTEM" | "EMAIL" | "BOTH";
  direction: "OUTBOUND" | "INBOUND" | "INTERNAL";
  sender: string | null;
  sender_name: string;
  recipients: Array<{id?:string;email:string;name:string;role?:string}>;
  subject: string;
  body: string;
  from_status: string;
  to_status: string;
  attachments: Array<{type:string;id:number;name:string;sha256:string;size:number}>;
  delivery_status: string | null;
  created_at: string;
  form_code?: string;
  form_name?: string;
  period_name?: string;
  submission_reference?: string;
  submission_version?: number | null;
  email_handoff?: { id:number; event:number; recipients:Array<{email:string;name?:string}>; subject:string; body:string; status:"AVAILABLE"|"OPENED"|"DEFERRED"; opened_at:string|null; deferred_at:string|null } | null;
}

export interface SubmissionComplianceFlag {
  id: number;
  flag_type: string;
  description: string;
  missing_field_count: number;
  completion_percentage: number;
  status: "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "RESOLVED";
  created_at?: string;
}

export interface FormWorkbookImport {
  id: number;
  form_code: string;
  name: string;
  version: string;
  sector: Sector;
  provider_category: ProviderCategory;
  frequency: Frequency;
  file_name: string;
  file_size: number;
  sha256: string;
  scan_status: "PENDING" | "CLEAN" | "INFECTED" | "ERROR";
  scan_engine: string;
  scan_details: string;
  parse_status: "PENDING" | "READY" | "FAILED" | "CONFIRMED";
  parser_version: string;
  detected_schema: {
    parser_version?: string;
    grouping?: { strategy:"worksheet-tabs"; isolation?:"worksheet-isolated"; visible_worksheet_count:number; engine?:"streaming" };
    sections?: Array<{
      section_code: string;
      title: string;
      instructions: string;
      worksheet_order: number;
      source: { sheet:string; sheet_index:number };
      row_visibility?: { policy:"visible-only"; visible_source_row_count:number; excluded_hidden_row_count:number };
      counts?: { scalar_field_count:number; table_count:number; grid_input_count:number };
      column_mapping: { detected:boolean; header_row:number|null; indicator_column:number|null; definition_column:number|null; data_type_column:number|null; unit_column:number|null; required_column:number|null; options_column:number|null; candidates:Array<{row:number;columns:Array<{column:number;label:string}>}> };
      headings: Array<{ heading_code:string; title:string; level:1|2|3; source_order:number; source_row:number; source:{sheet:string;row:number}; parser_version:string }>;
      fields: Array<{ source_order:number; field_code:string; heading_code:string; label:string; field_type:FieldType; unit:string; is_required:boolean; help_text:string; formula:string; options:string[]; source:{sheet:string;row:number;heading:string}; parser_version:string }>;
      grids: Array<{ source_order:number; grid_code:string; title:string; row_mode:"FIXED"|"REPEATABLE"; min_rows:number; instructions:string; columns:Array<{column_code:string;label:string;field_type:FieldType;unit:string;is_required:boolean;source?:{sheet:string;row:number}}>; fixed_rows:string[]; fixed_row_sources?:Array<{label:string;source:{sheet:string;rows:number[]}}>; source:{sheet:string;row:number;heading:string}; parser_version:string }>;
    }>;
  };
  warnings: Array<{ code:string; severity:string; message:string }>;
  mapping_decisions: Record<string, unknown>;
  resulting_template_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface FormCodeCatalogEntry {
  id: number;
  code: string;
  name: string;
  frequency: Frequency;
  source_filename: string;
  code_status: "CONFIRMED" | "PROVISIONAL";
  next_version: string;
}

export interface ProviderWorkspaceSummary {
  role: "PROVIDER_DATA_ENTRY" | "PROVIDER_APPROVER";
  action_required: number;
  drafts: number;
  awaiting_data_entry: number;
  due_soon: number;
  overdue: number;
  awaiting_approver: number;
  nca_corrections: number;
  returned_to_data_entry: number;
  recently_submitted: number;
  open_compliance_flags: number;
  flagged_submissions: number;
  penalty_amount_ghs: string;
  penalty_obligation_count: number;
}

export interface AuditEvent {
  id: number;
  user_email: string;
  role: string;
  organization: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before_value: unknown;
  after_value: unknown;
  ip_address: string | null;
  timestamp: string;
  previous_hash: string;
  event_hash: string;
}

export interface AuditAnchor {
  id: number;
  anchor_date: string;
  first_event_id: number | null;
  last_event_id: number | null;
  event_count: number;
  root_hash: string;
  signature: string;
  exported_reference: string;
  created_at: string;
}

export interface SubmissionNotificationSummary {
  unread: number;
  total: number;
  by_event_type: Record<string, number>;
  pending_approval: number;
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
  sector: Sector;
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

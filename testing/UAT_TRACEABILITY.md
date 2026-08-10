# NCA UAT Traceability Matrix

**Baseline:** `NCA_Complete_Testing_Guide (1).docx`
**Implementation plan:** `NCA_Testing_and_Remediation_Plan.docx`
**Branch:** `testing_fix`
**Local target:** `http://127.0.0.1:3001` / `http://127.0.0.1:8001`
**Review date:** 2026-08-05

## Status legend

- **PASS-AUTO** — covered by a repeatable backend/API or compile/build check.
- **PASS-UI** — exercised in the local Chromium-based in-app browser.
- **PASS-LIMITED** — the implemented behavior passed locally, but part of the external compatibility matrix is unavailable in this environment.
- **PENDING-UAT** — requires a named human tester or external application/device and is not represented as completed.

## Matrix

| ID | Acceptance scenario | Status | Evidence |
|---|---|---|---|
| UAT-001 | Login with valid credentials | PASS-AUTO / PASS-UI | API smoke login; local browser login and role routing. |
| UAT-002 | Login with wrong password | PASS-AUTO | `UserManagementRemediationTests.test_login_wrong_password_and_logout_blacklists_refresh_token`; API smoke. |
| UAT-003 | Logout and block return to authenticated pages | PASS-AUTO | Refresh token blacklist regression test; role route guards and 401 token clearing. Browser Back behavior remains part of human sign-off. |
| UAT-004 | NCA dashboard overview | PASS-AUTO / PASS-UI | Dashboard summary/chart endpoints; local dashboard visual check. |
| UAT-005 | Notification bell counts | PASS-UI | Top-bar dropdown inspected locally; values come from dashboard summary and active-period APIs. |
| UAT-006 | View providers list | PASS-AUTO / PASS-UI | Provider list API smoke; local provider table check. |
| UAT-007 | Search providers | PASS-AUTO / PASS-UI | Provider search API smoke; local filtering check. |
| UAT-008 | Filter providers by category | PASS-AUTO / PASS-UI | Category API smoke and local filter; sector filter also verified. |
| UAT-009 | Provider detail page | PASS-AUTO | Provider detail API smoke and page production build. |
| UAT-010 | Provider sees only own organization | PASS-AUTO | Organization-scoped provider/submission/compliance regressions. |
| UAT-011 | NCA views all submissions | PASS-AUTO / PASS-UI | Expected-submission API smoke and NCA submissions page. |
| UAT-012 | Search submissions | PASS-AUTO | API smoke search by provider name. |
| UAT-013 | Filter submissions by status | PASS-AUTO | API smoke status filter. |
| UAT-014 | Provider starts submission | PASS-AUTO / PASS-UI | `test_data_entry_can_start_and_reload_saved_values`; local Data Entry user started a Not Started form and reached the section editor. |
| UAT-015 | Fill and persist fields | PASS-AUTO | Save/reload regression plus centralized readiness calculation. |
| UAT-016 | Non-filled status requires explanation | PASS-AUTO | `test_non_filled_required_value_needs_explanation`. |
| UAT-017 | Navigate form sections | PASS-AUTO | Form template returns ordered sections; provider page and stepper compile in production build. Human interaction remains part of sign-off. |
| UAT-018 | Upload Excel backup | PASS-AUTO | Authenticated multipart, organization-scope, filename, and refreshed-list regression. |
| UAT-019 | Submit complete form to approver | PASS-AUTO | Incomplete blocker and complete transition regressions; UI uses `can_submit`. |
| UAT-020 | Approver reviews and submits to NCA | PASS-AUTO / PASS-UI | Approver read-only and return/official-submit regressions; local approver page showed disabled fields and only Return/Submit workflow controls. |
| UAT-021 | NCA reviews and approves | PASS-AUTO | Submitted-state guard and approve regression. |
| UAT-022 | NCA requests correction | PASS-AUTO | Correction note/edit/reapproval/resubmission regression. |
| UAT-023 | View compliance flags | PASS-AUTO / PASS-UI | Compliance list regression and local viewer inspection. |
| UAT-024 | Acknowledge compliance flag | PASS-AUTO | `ComplianceWorkflowTests.test_admin_can_list_acknowledge_resolve_and_generate_email`; API smoke. |
| UAT-025 | Resolve compliance flag | PASS-AUTO | Compliance transition regression. |
| UAT-026 | Generate compliance email | PASS-AUTO | Template substitution, recipient, and draft-log regression. SMTP delivery is outside scope. |
| UAT-027 | Provider sees own compliance alerts only | PASS-AUTO | Two-organization compliance isolation regression. |
| UAT-028 | Create NCA user | PASS-AUTO | Viewer/user creation regression, password hashing, and capability flags. |
| UAT-029 | Deactivate user | PASS-AUTO | Toggle-active and inactive-login rejection regression. |
| UAT-030 | Create provider user with organization | PASS-AUTO / PASS-UI | Writable `organization_id`, validation, and linked-user regression; provider organization selector verified locally. |
| UAT-031 | Download CSV | PASS-LIMITED | CSV endpoint and authenticated browser download passed locally; Chrome/Chromium covered. Edge, Firefox, and WebKit/Safari remain PENDING-UAT. |
| UAT-032 | CSV contains real values and opens in spreadsheet tools | PASS-LIMITED | BOM, Unicode, CRLF, real values, formula neutralization, headers, filename, and empty-export regressions. Microsoft Excel and Google Sheets visual import remain PENDING-UAT. |
| UAT-033 | Provider cannot access NCA area | PASS-AUTO / PASS-UI | NCA APIs deny provider roles; navigating a logged-in provider to `/dashboard` redirected to `/provider/dashboard` before protected content rendered. |
| UAT-034 | Provider cannot enumerate another provider submission | PASS-AUTO | 404 regressions for expected submission, version, values, completion, uploads, review history, and workflow actions. |
| UAT-035 | Immutable form family/version and source-map approval | PENDING-UAT | APIs and publication gates implemented; approved source forms and source-owner sign-off remain external. |
| UAT-036 | DC-DBS05 activation remains blocked | PASS-AUTO | Frequency decision defaults to `PENDING_DECISION`; explicit source-owner decision API required. |
| UAT-037 | Typed validation and correction-scoped editing | PASS-AUTO | Allow-listed rule engine, validation evidence, correction cloning, locking and diff APIs. |
| UAT-038 | Official receipt and private file controls | PASS-AUTO | Frozen PDF receipt, hashes, authenticated download, upload quarantine and scan gate. |
| UAT-039 | Email provider-neutral queue | PASS-AUTO | Versioned templates, placeholder validation, outbox and delivery-event contracts; real sending disabled. |
| UAT-040 | Governance readiness and retention dry run | PASS-AUTO | Approval gates, legal holds, evidence-only candidate preview and deletion-disabled default. |
| UAT-041 | Backup and isolated restore verification | PENDING-UAT | pgBackRest configuration/runbooks delivered; storage credentials, RPO/RTO and recovery exercise evidence required. |
| UAT-042 | Chrome, Edge, Firefox and Safari matrix | PENDING-UAT | Named human/browser execution required. |
| UAT-043 | Excel, Google Sheets, CSV, XLSX and PDF comparison | PENDING-UAT | Shared canonical row iterator implemented; external application sign-off required. |
| UAT-044 | Data requester catalog/request/approval/download/expiry | PASS-AUTO | Requester isolation and Admin-only decision APIs covered; named business UAT remains required. |
| UAT-045 | G-25 | NOT APPLICABLE | Explicitly excluded by the approved remediation plan. |

## Acceptance summary

- Critical provider workflow and organization-isolation cases UAT-014 through UAT-022 and UAT-034 have repeatable regression coverage.
- CSV output compatibility safeguards are repeatably verified; remaining external browser/spreadsheet checks are explicitly recorded as PENDING-UAT rather than inferred.
- Governance sign-off, Corporate Communications approval, IT readiness, and the external compatibility matrix remain human-controlled release gates in the Word plan.

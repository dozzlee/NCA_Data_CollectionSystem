# API Summary

All endpoints are below `/api/v1/`. Browser authentication uses rotating JWTs in Secure, HttpOnly, SameSite cookies; unsafe methods require CSRF. This summary lists publication-critical interfaces.

## Authentication

- `GET auth/csrf/`, `POST auth/login/`, `POST auth/refresh/`, `POST auth/logout/`, `GET auth/me/`
- `POST auth/change-password/`
- Admin: `POST auth/users/{id}/reset-password/`

## Forms, periods and assignments

- Form families/templates, sections, fields, options, grids, columns, fixed rows and validated rules
- Template clone, source-map decision, gap recalculate/resolve and publication actions
- `POST form-workbook-imports/`, `GET|PATCH form-workbook-imports/{id}/` and `POST form-workbook-imports/{id}/confirm/` provide private, scanned `.xlsx` schema import and reviewed draft generation. Workbook cell values are never provider-answer defaults.
- `GET form-templates/{id}/assignment-preview/` and `GET|POST form-templates/{id}/assignments/` preview and create recurring or exact one-period provider assignments.
- `GET periods/{id}/assignment-preview/` resolves the exact recurring/manual obligations that period activation will create.
- Provider/form assignments with CSV dry-run/commit and import template
- Reporting periods support monthly, quarterly and annual creation while retaining historical semi-annual records; activation, reminders, deadline-change and submission-override decisions remain available.

## Submissions

- `GET provider-workspace/summary/` returns full-provider queue counts independent of pagination.
- `GET provider-workspace/submissions/?queue=...` supports paginated role queues plus search/form/period/status/deadline/correction filters and server-calculated permitted actions.
- `GET submissions/{id}/provider-review-data/` returns the exact immutable schema, values, readiness, corrections, files, versions, timeline, approval and provider edit batches to authorized tenant users.
- `POST submissions/{id}/submit-for-approval/`
- `POST submissions/{id}/provider-review/request-correction/`
- `POST submissions/{id}/provider-review/resubmit/`
- `POST submissions/{id}/provider-review/approve/` requires `attestation: true`; `change_summary` is required when the Approver edited values after handoff.
- `PUT submissions/{id}/sections/{section_code}/values/` with `revision`
- `GET submissions/{id}/review-data/`, `GET submissions/{id}/timeline/`
- `GET submission-notifications/summary/`, plus notification list and mark-read/mark-all-read actions.
- Data Entry edits only `DRAFT` and `PROVIDER_CHANGES_REQUESTED`; Approvers edit only `PENDING_APPROVAL`, `PROVIDER_RESUBMITTED` and cloned `CORRECTION_REQUESTED` versions. Every Approver section save creates an immutable sensitive before/after edit batch; the central audit receives identifiers/count/hash only.
- Existing transition paths are compatibility wrappers and emit the same audit/workflow records.

## Dashboard, exports and private files

- `GET industry-dashboard/data/` returns role-sanitized aggregates.
- `GET industry-dashboard/export/?format=xlsx` returns a generated aggregate workbook.
- Operational approved-data exports support CSV/PDF and canonical filters.
- KMZ, Excel backups, receipts and request artifacts download only through authenticated streaming endpoints after authorization/scan/readiness checks.

## Data requests

- Metadata-only catalog; own/all request list by role; request actions for review, clarification, approval, rejection, withdrawal, retry and authenticated download.
- Data-request notifications support list, mark-one and mark-all read.

## Governance and support

- Retention policies, legal holds, disposition previews, backup/restore evidence, task history, audit verification/readiness and support ticket lifecycle.

Refer to DRF route definitions for the complete generated interface. Role and tenant checks are authoritative at the API layer.

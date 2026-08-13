# Product

## Purpose

The NCA Data Collection and Compliance Management System is a governed regulatory portal. Providers enter structured returns, their Approvers officially submit them, NCA reviews and corrects them, internal divisions request released data, and every material action is traceable.

## Roles

1. NCA Admin — complete access.
2. NCA Officer — operational Admin parity except Users, divisions and Data Requests.
3. Provider Approver — server-counted approval/NCA-correction queues, permitted-stage editing with immutable diffs, targeted returns, attested official submission, compliance contact and technical support.
4. Provider Data Entry — shared provider draft/returned-work queue, optimistic autosave/manual save, read-only corrective compliance visibility and technical-support tracking.
5. NCA Data Requester — metadata catalog, own data requests, notifications and released artifacts.

## Regulatory forms

Seven immutable PRD Section 11 families are maintained. Corrected versions are MNO 3.0, ISP06 3.0, ITC04 3.0, TB02 3.0, Tower 2.0, DBS05 2.0 and SUB03 2.0. Tower's code is provisional. Only DBS05 requires topology KMZ. Private Excel backup remains a secured submission extension. Separately, NCA staff may import a clean `.xlsx` as schema provenance for a new form family; imported cell values never become provider answers.

## Form Builder and assignment

Admins and Officers can create arbitrary uppercase form codes manually or generate a reviewed draft from a private workbook. Visible worksheets become sections and detected tables/labels become editable grids and fields. Publication remains subject to structural and approval gates: Admin-created drafts may be published by Admin, while Officer-created drafts require Admin publication approval. Published forms can be sent through recurring effective-dated assignments or exact one-period assignments. Monthly, quarterly and annual schedules are supported, and historical semi-annual periods remain readable.

## Core principles

- Historical official submissions and form versions are immutable.
- Corrections are targeted, versioned and auditable.
- Approver value edits retain sensitive before/after evidence within the provider/NCA boundary; general audit records carry target IDs, counts and hashes rather than copied raw values.
- Status, validation and deadlines remain explicit.
- Provider tenancy and role separation are enforced server-side.
- Private data is never published under `/media/`.
- Dashboard access is aggregate-only for providers and requesters.
- Email sending and automated disposition remain disabled until approved external configuration exists.

WCAG 2.1 AA is the minimum interaction target: keyboard navigation, visible focus, explicit labels and non-colour status cues.

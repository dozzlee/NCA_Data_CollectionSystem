# Product

## Purpose

The NCA Data Collection and Compliance Management System is a governed regulatory portal. Providers enter structured returns, their Approvers officially submit them, NCA reviews and corrects them, internal divisions request released data, and every material action is traceable.

## Roles

1. NCA Admin — complete access.
2. NCA Officer — operational Admin parity except Users, divisions and Data Requests.
3. Provider Approver — provider review, official submission, compliance contact and technical support.
4. Provider Data Entry — data entry and technical support only.
5. NCA Data Requester — metadata catalog, own data requests, notifications and released artifacts.

## Regulatory forms

Seven immutable PRD Section 11 families are maintained. Corrected versions are MNO 3.0, ISP06 3.0, ITC04 3.0, TB02 3.0, Tower 2.0, DBS05 2.0 and SUB03 2.0. Tower's code is provisional. Only DBS05 requires topology KMZ. Private Excel backup is a secured operational extension, not a spreadsheet-import workflow.

## Core principles

- Historical official submissions and form versions are immutable.
- Corrections are targeted, versioned and auditable.
- Status, validation and deadlines remain explicit.
- Provider tenancy and role separation are enforced server-side.
- Private data is never published under `/media/`.
- Dashboard access is aggregate-only for providers and requesters.
- Email sending and automated disposition remain disabled until approved external configuration exists.

WCAG 2.1 AA is the minimum interaction target: keyboard navigation, visible focus, explicit labels and non-colour status cues.

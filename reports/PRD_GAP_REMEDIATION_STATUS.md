# NCA PRD Gap Remediation Status

Implemented on 5 August 2026 in this repository only. G-25 is intentionally excluded.

## Delivered controls

- Immutable form families/versions, source hashes, maker/checker publication, DC-DBS05 frequency gate, clone/preview and allow-listed validation rules with persisted results.
- Versioned reminder policies, approval-backed deadline changes, scoped readiness overrides and idempotent operational task evidence.
- Correction cloning and locking, correction diffs/checklists, explicit regulatory review, non-filled dispositions and hashed private submission receipts with transactional outbox creation.
- Versioned compliance templates, placeholder validation, durable queue/delivery contracts and no manual `SENT` state.
- Private upload quarantine, SHA-256, ClamAV adapter and authenticated clean-file downloads outside `/media`.
- Shared scalar/grid export rows for operational and requester CSV/XLSX/PDF outputs, including workflow, disposition, review and compliance context.
- Dashboard metric catalogue, category/form/officer/due-state filters, centralized hash-chained audit records and daily signed anchors.
- Retention policy approval, legal holds, disposition previews, backup/restore evidence, operational task history and a read-only readiness view.
- Production HTTPS/security startup gates and internal support ownership, acknowledgement, SLA, requester updates and resolution history.

## Deliberately inactive launch controls

Production activation remains blocked until NCA supplies approved production source forms, the DC-DBS05 frequency decision, penalty wording, Graph shared-mailbox configuration, secure secrets/origins, immutable storage credentials, RPO/RTO targets and named UAT sign-offs.

Automated record disposition is disabled by default. A dry run is evidence-only; it cannot delete records. Data-request expiry blocks download immediately, while physical deletion remains retention-policy and legal-hold gated.

## Recovery boundary

The repository contains pgBackRest-compatible configuration, encrypted/immutable storage requirements and recovery runbooks. A successful backup or restore is never fabricated by the application: evidence must be produced by the configured external recovery environment and recorded through the governance APIs.

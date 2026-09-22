# NCA Publication Smoke Test

Record tester, date, release identifier and environment. A failed mandatory item blocks publication.

## Infrastructure and security

- [ ] PostgreSQL, Redis, backend, frontend, worker, beat, ClamAV and Nginx are healthy.
- [ ] Production settings pass `manage.py check --deploy`; no unsafe defaults or automatic demo seeding occurs.
- [ ] TLS redirect, secure HttpOnly auth cookies, CSRF, HSTS, CORS, host and proxy-CIDR rules behave as configured.
- [ ] Repeated failed login locks the account; Admin temporary-password reset forces a password change.
- [ ] `/media/` does not expose private uploads or generated files.

## Seven forms and provider workflow

- [ ] Correct active versions are MNO 3.0, ISP06 3.0, ITC04 3.0, TB02 3.0, Tower 2.0, DBS05 2.0 and SUB03 2.0.
- [ ] Tower code is visibly provisional; topology KMZ appears only on DBS05.
- [ ] Data Entry sees server-calculated shared-queue counts, saves scalar/grid snapshots through autosave/manual save, sees precise validation, and stale revisions preserve local values with latest-editor details.
- [ ] `DRAFT → PENDING_APPROVAL`; only the same provider's Approver sees the item.
- [ ] A correction can target multiple sections/fields/grid cells, returns only permitted work to Data Entry, and resubmission retains history and targets.
- [ ] Approver can edit only approval/NCA-correction stages; each save has immutable before/after evidence and a non-sensitive audit hash.
- [ ] Approver readiness/upload/correction check plus accuracy attestation creates the official `SUBMITTED`/`RESUBMITTED` version; an Approver edit requires a change summary and Data Entry cannot do this.
- [ ] Navigation notification/pending counts, direct links, mark-one/all-read, history submitted timestamps, receipt links and own technical-ticket history are correct.
- [ ] NCA review uses the exact stored template, clones regulatory corrections, locks unaffected content and preserves official history.

## Form Builder and assignment

- [ ] Admin/Officer can create a manual draft with an arbitrary normalized code, name, version, sector, provider type and monthly/quarterly/annual frequency.
- [ ] A private `.xlsx` larger than 20 MB, unreadable/encrypted file, unsafe scan result or unresolved blocking mapping warning cannot be confirmed.
- [ ] Import preview contains sections/fields/grids/formulas/provenance but no workbook answer values; the reviewed mapping creates a draft, never a published form.
- [ ] Only an Admin can publish; an Officer-created form remains pending Admin publication approval.
- [ ] Assignment preview lists exact pairs, duplicates, exclusions and provider mismatches; mismatch override requires a reason.
- [ ] Recurring assignments renew in matching periods using the latest approved version; manual assignments bind an exact version to one non-closed period and remain idempotent.
- [ ] Quarterly periods require quarter 1–4, and activation creates only exact recurring/manual obligations plus provider notifications.

## Roles and features

- [ ] Admin has all functions; Officer has operational parity except Users/divisions/Data Requests.
- [ ] Provider Data Entry has no compliance/general contact action; Approver retains it.
- [ ] Requester sees only catalog metadata, own requests/notifications and released artifacts.
- [ ] All roles can view/filter aggregate Industry Dashboard data and download aggregate XLSX.
- [ ] Only Admin/Officer can update dashboard source/configuration; other roles cannot obtain source or provider-level rows.

## Files, exports and audit

- [ ] Excel/KMZ upload begins quarantined, stores SHA-256/scan metadata and cannot download before `CLEAN`.
- [ ] Operational CSV/PDF includes only NCA-approved versions, scalar/grid rows, statuses and review/compliance context.
- [ ] Admin and owning requester download the exact released request artifact; Officer and unrelated requesters are denied.
- [ ] Workflow, authentication, validation, upload, download and export events are hash chained; daily anchor verifies.
- [ ] Outbound messages remain `DRAFT`/`QUEUED` when no mail provider is configured.

## Recovery and sign-off

- [ ] Most recent backup and isolated restore meet approved RPO/RTO; representative private-file hashes match.
- [ ] Retention deletion is disabled unless every policy and approval gate is complete.
- [ ] Named browser/spreadsheet UAT and NCA business/provider sign-off are attached.

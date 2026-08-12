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
- [ ] Data Entry saves scalar and grid snapshots, sees precise validation, and stale revisions return a conflict.
- [ ] `DRAFT → PENDING_APPROVAL`; only the same provider's Approver sees the item.
- [ ] A targeted correction returns it to Data Entry; resubmission retains history and targets.
- [ ] Approver readiness check creates the official `SUBMITTED` version; Data Entry cannot do this.
- [ ] NCA review uses the exact stored template, clones regulatory corrections, locks unaffected content and preserves official history.

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

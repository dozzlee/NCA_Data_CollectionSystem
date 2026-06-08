# NCA Data Collection System — Production Smoke Test

Run this checklist after every fresh deployment or upgrade. Each item should pass before handing the system over to users.

**Tester:** ________________  
**Date:** ________________  
**Server IP / URL:** ________________  
**Commit:** ________________

---

## 1. Infrastructure

- [ ] `docker compose -f docker-compose.prod.yml ps` — all four services (`db`, `backend`, `frontend`, `nginx`) show **Up**
- [ ] `make logs-backend` — no Python tracebacks or migration errors on startup
- [ ] `make logs-nginx` — no upstream connection errors
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://<SERVER_IP>/` returns **200**
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://<SERVER_IP>/api/v1/auth/login/` returns **405** (POST only)

---

## 2. Authentication

- [ ] Login page loads at `http://<SERVER_IP>/login`
- [ ] Incorrect password → error message shown, no crash
- [ ] Correct NCA Admin credentials → redirect to `/dashboard`
- [ ] JWT token stored in `localStorage` (`access_token`, `refresh_token`)
- [ ] Navigating to `/dashboard` while logged out → redirect to `/login`

---

## 3. NCA Dashboard

- [ ] Dashboard loads without blank panels or console errors
- [ ] All 4 stat cards render (may show 0 if no data yet)
- [ ] All 4 charts render without JavaScript errors (may show empty state)
- [ ] Period selector in filter bar is present

---

## 4. Providers

- [ ] `/providers` page loads — table visible (empty or with data)
- [ ] Search box filters results
- [ ] Category and status dropdowns work
- [ ] Click "View →" on a provider → detail page loads
- [ ] Edit mode: click "Edit Provider", change a field, click "Save Changes" → success toast, change persists on reload

---

## 5. Periods

- [ ] `/periods` page loads — table visible
- [ ] "+ New Period" form opens, fills, submits → period appears in list with DRAFT status
- [ ] Click "View →" on a DRAFT period → detail page loads
- [ ] "Activate Period" button present on DRAFT period; confirm dialog appears
- [ ] After activation: period status changes to ACTIVE, expected submissions table populates

---

## 6. Submissions (Provider Flow)

_Log in as a provider user for these steps._

- [ ] Provider dashboard loads at `/dashboard` — submission list visible
- [ ] Overdue submissions show red banner (if any exist)
- [ ] Click "Start" on a NOT_STARTED submission → form entry page loads
- [ ] Section stepper visible on the left with all sections listed
- [ ] Fill a text field → save → completion % updates
- [ ] Non-filled status dropdown (Not Applicable, etc.) works and shows explanation field
- [ ] Conditional field: verify a conditional field only appears when its parent field has the required value
- [ ] "Submit for Approval" button visible when all required fields are filled
- [ ] Submit for approval → workflow status changes to PENDING_APPROVAL

---

## 7. Form Engine

- [ ] Text, number, date, boolean, select, textarea field types all render correctly
- [ ] Formula fields are read-only
- [ ] Declaration (checkbox) field works
- [ ] Fixed-row grid (e.g. Ghana 16 regions) renders all 16 rows
- [ ] Repeatable grid: "Add Row" adds a new row; "Remove" deletes it
- [ ] KMZ upload panel is **only** visible on DC-DBS05 and DC-SUB03 forms — not on any other form

---

## 8. NCA Review

- [ ] Navigate to a SUBMITTED submission → review page loads
- [ ] Approve action → status changes to APPROVED
- [ ] Reject action → status changes to REJECTED
- [ ] Request Correction → status changes to CORRECTION_REQUESTED
- [ ] Internal note → appears in review history timeline
- [ ] Provider comment → appears with "provider-visible" indicator

---

## 9. Compliance

- [ ] `/compliance` page loads — summary cards visible
- [ ] Overdue list populates (if any exist)
- [ ] Select a provider, choose a template, click "Generate Draft" → email draft created and appears in email log
- [ ] "Mark Sent" on an email draft → status changes to SENT

---

## 10. Exports

- [ ] `/exports` page loads
- [ ] Select filters and click "Generate CSV" → file downloads (or success message if no data)
- [ ] Export log entry created after each export action

---

## 11. File Uploads

- [ ] On a DC-DBS05 or DC-SUB03 submission: KMZ panel accepts a `.kmz` file
- [ ] Non-KMZ file (e.g. `.pdf`) is rejected with an error message
- [ ] Excel backup panel accepts `.xlsx` / `.xls`
- [ ] Non-Excel file is rejected with an error message
- [ ] File sizes above 50 MB are rejected server-side

---

## 12. Audit Trail

- [ ] Login, submit a section, and approve a submission
- [ ] In Django Admin (`/admin/audit/auditevent/`) → confirm AuditEvent rows exist for each action
- [ ] No AuditEvent rows can be updated or deleted via Admin (verify save is blocked)

---

## 13. Session & Security

- [ ] After 15 minutes of inactivity, session warning modal appears (or verify JWT expiry is correctly configured)
- [ ] "Stay signed in" refreshes the token and dismisses the modal
- [ ] "Sign out" redirects to `/login`
- [ ] `/api/v1/dashboard/summary/` without a token → **401 Unauthorized**
- [ ] Provider user cannot access `/api/v1/providers/` (NCA-only endpoint) → **403 Forbidden**

---

## 14. Feedback and Issue Reporting

- [ ] `POST /api/v1/feedback/` with a valid token → **201 Created**
- [ ] `POST /api/v1/issues/` with a valid token → **201 Created**
- [ ] Records appear in Django Admin under Feedback / System Issues

---

## Sign-off

All items checked: **Yes / No**

Signed off by: ________________  
Date: ________________

If any item fails, document the failure and do not hand over to users until resolved.

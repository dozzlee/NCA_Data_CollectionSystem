# NCA Data Collection System — Testing Framework

**Version:** 1.0  
**Last Updated:** 2026-06-16  
**System URL (Live):** https://codedematrix-datacollection.hf.space/  
**System URL (Local):** http://localhost:3000  

---

## Overview

This document covers two levels of testing:

| Level | Who runs it | What it checks |
|-------|-------------|----------------|
| **API Tests** | Developer / QA | All backend endpoints return correct data and enforce security rules |
| **User Acceptance Tests (UAT)** | NCA staff + Provider testers | The platform works correctly from a real user's perspective |

---

## Part A — Automated API Tests

### How It Works

The API test script (`testing/api_test.sh`) makes real HTTP calls to the system. It does not mock anything — it hits the actual running server and checks that:
- The right HTTP status codes come back
- Authentication and authorisation are enforced
- Role-based access control (RBAC) works (providers can't see other providers' data)
- Data is returned in the expected format

### Running Against Local Server

```bash
# Make sure both servers are running first
# Then run:
bash testing/api_test.sh

# Or explicitly:
bash testing/api_test.sh http://localhost:8000
```

### Running Against Live Deployment

```bash
bash testing/api_test.sh https://codedematrix-datacollection.hf.space
```

### What the Script Tests

| Section | Endpoints Tested |
|---------|-----------------|
| Health Check | Server reachable |
| Authentication | Login, bad credentials, token, profile, unauthenticated rejection |
| Providers | List, search, filter by category, get single, RBAC |
| Submissions | List, search, filter by status, get single, RBAC |
| Compliance | List flags, filter by status, acknowledge a flag |
| Users | List users, RBAC (provider blocked) |
| Exports | CSV export endpoint |
| Audit | Audit log accessible to NCA only |

### Reading the Results

```
✓ PASS  GET /providers/ list (HTTP 200)
✗ FAIL  Provider RBAC on submissions
         Expected 403, got 200
– SKIP  Export test — Need provider ID from earlier tests
```

A full run with no failures looks like:
```
RESULTS
Passed:  22
Failed:  0
Skipped: 2
```

---

## Part B — User Acceptance Testing (UAT)

These tests are to be done by actual users in the browser. Each scenario has:
- A **role** (who logs in)
- **Steps** to follow
- **Expected result** (what should happen)
- A **pass/fail checkbox**

### Test Accounts

| Role | Email | Password |
|------|-------|----------|
| NCA Admin | admin@nca.org.gh | testpass123 |
| NCA Officer | officer.asante@nca.org.gh | testpass123 |
| Provider (Data Entry) | dataentry@vodafone.com.gh | testpass123 |
| Provider (Approver) | admin@vodafone.com.gh | testpass123 |

---

### Module 1: Authentication

#### UAT-001 — Login with valid credentials
- **Role:** Any
- **Steps:**
  1. Go to the system URL
  2. Enter a valid email and password from the table above
  3. Click Login
- **Expected:** Redirected to dashboard, name appears in the sidebar
- **Pass / Fail:** ___

#### UAT-002 — Login with wrong password
- **Role:** Any
- **Steps:**
  1. Enter a valid email but wrong password
  2. Click Login
- **Expected:** Error message shown, not logged in
- **Pass / Fail:** ___

#### UAT-003 — Logout
- **Role:** Any
- **Steps:**
  1. Log in successfully
  2. Click the logout button (bottom of sidebar)
- **Expected:** Returned to login page, cannot go back with browser Back button
- **Pass / Fail:** ___

---

### Module 2: Dashboard

#### UAT-004 — NCA Dashboard overview
- **Role:** NCA Admin or NCA Officer
- **Steps:**
  1. Log in
  2. View the Dashboard page
- **Expected:** See counts for submissions (by status), overdue submissions, active periods, recent compliance alerts
- **Pass / Fail:** ___

#### UAT-005 — Notification bell
- **Role:** NCA Admin
- **Steps:**
  1. Click the bell icon (top right)
- **Expected:** Dropdown shows overdue submissions, correction requests, pending approvals with counts
- **Pass / Fail:** ___

---

### Module 3: Providers

#### UAT-006 — View providers list
- **Role:** NCA Admin
- **Steps:**
  1. Click "Providers" in the sidebar
- **Expected:** Table of providers showing name, category, licence number, status
- **Pass / Fail:** ___

#### UAT-007 — Search providers
- **Role:** NCA Admin
- **Steps:**
  1. On the Providers page, type "Vodafone" in the search box
- **Expected:** List filters to show only Vodafone-related providers
- **Pass / Fail:** ___

#### UAT-008 — Filter by category
- **Role:** NCA Admin
- **Steps:**
  1. On the Providers page, select "Mobile Network Operator" from the category dropdown
- **Expected:** Only MNO providers are shown
- **Pass / Fail:** ___

#### UAT-009 — Provider detail page
- **Role:** NCA Admin
- **Steps:**
  1. Click on any provider in the list
- **Expected:** Provider detail page loads showing company info, submission history, compliance status
- **Pass / Fail:** ___

#### UAT-010 — Provider cannot see other providers
- **Role:** Provider (Data Entry)
- **Steps:**
  1. Log in as dataentry@vodafone.com.gh
  2. Click "Providers" or look for provider list
- **Expected:** Provider only sees their own organisation — no list of all providers
- **Pass / Fail:** ___

---

### Module 4: Submissions

#### UAT-011 — View all submissions (NCA)
- **Role:** NCA Officer
- **Steps:**
  1. Click "Submissions" in the sidebar
- **Expected:** Table of all provider submissions with status badges and due dates
- **Pass / Fail:** ___

#### UAT-012 — Search submissions
- **Role:** NCA Officer
- **Steps:**
  1. On Submissions page, type a provider name in the search box (e.g. "MTN")
- **Expected:** Results filter in real time, showing only matching submissions
- **Pass / Fail:** ___

#### UAT-013 — Filter submissions by status
- **Role:** NCA Officer
- **Steps:**
  1. Select "Draft" from the status filter dropdown on Submissions
- **Expected:** Only DRAFT submissions shown
- **Pass / Fail:** ___

#### UAT-014 — Start a submission (Provider)
- **Role:** Provider (Data Entry)
- **Steps:**
  1. Log in as dataentry@vodafone.com.gh
  2. Click on a form listed as "Not Started"
  3. Click "Start form"
- **Expected:** Form opens with sections listed on the left, first section active
- **Pass / Fail:** ___

#### UAT-015 — Fill in form fields
- **Role:** Provider (Data Entry)
- **Steps:**
  1. On an open form, fill in values for at least 3 required fields
  2. Click "Save progress"
- **Expected:** "Saved" confirmation appears briefly, no data loss on page reload
- **Pass / Fail:** ___

#### UAT-016 — Mark a field as Not Applicable
- **Role:** Provider (Data Entry)
- **Steps:**
  1. On an open form, find a required field
  2. In the status dropdown next to the field, select "Not Applicable"
  3. Enter an explanation
  4. Save
- **Expected:** Field clears, explanation box appears, saves successfully
- **Pass / Fail:** ___

#### UAT-017 — Navigate between sections
- **Role:** Provider (Data Entry)
- **Steps:**
  1. On an open form, click "Next" to move to section 2, then "Previous"
- **Expected:** Correct sections load, completion percentage updates in stepper on left
- **Pass / Fail:** ___

#### UAT-018 — Upload Excel backup
- **Role:** Provider (Data Entry)
- **Steps:**
  1. On an open form (DRAFT status), scroll to the "Excel Backup" panel at the bottom of any section
  2. Upload an .xlsx file (any Excel file)
- **Expected:** Upload progress shown, file listed under "Previous Uploads" after success
- **Pass / Fail:** ___

#### UAT-019 — Submit to Approver
- **Role:** Provider (Data Entry)
- **Steps:**
  1. Fill in all required fields in a form
  2. Click "Submit to Approver"
- **Expected:** Status changes to "Pending Approval", button disappears, form becomes read-only
- **Pass / Fail:** ___

#### UAT-020 — Approver reviews and submits to NCA
- **Role:** Provider (Approver)
- **Steps:**
  1. Log in as admin@vodafone.com.gh
  2. Find a submission in "Pending Approval" status
  3. Review it, then click "Submit to NCA"
- **Expected:** Status changes to "Submitted", NCA is notified
- **Pass / Fail:** ___

#### UAT-021 — NCA reviews a submission
- **Role:** NCA Officer
- **Steps:**
  1. Find a SUBMITTED submission
  2. Click Review
  3. Review values, then click Approve
- **Expected:** Submission moves to APPROVED status
- **Pass / Fail:** ___

#### UAT-022 — NCA requests a correction
- **Role:** NCA Officer
- **Steps:**
  1. Find a SUBMITTED submission
  2. Click Review
  3. Click "Request Correction" and add a note
- **Expected:** Submission moves to CORRECTION_REQUESTED, provider can see the note and edit again
- **Pass / Fail:** ___

---

### Module 5: Compliance

#### UAT-023 — View compliance flags (NCA)
- **Role:** NCA Admin
- **Steps:**
  1. Click "Compliance" in the sidebar
- **Expected:** List of OPEN/ACKNOWLEDGED flags showing provider name, missing field count, completion percentage bar
- **Pass / Fail:** ___

#### UAT-024 — Acknowledge a flag
- **Role:** NCA Admin
- **Steps:**
  1. On the Compliance page, find an OPEN flag
  2. Click "Acknowledge"
- **Expected:** Flag status changes to ACKNOWLEDGED immediately
- **Pass / Fail:** ___

#### UAT-025 — Resolve a flag
- **Role:** NCA Admin
- **Steps:**
  1. Find an ACKNOWLEDGED flag
  2. Click "Resolve"
- **Expected:** Flag disappears from the active list (status = RESOLVED)
- **Pass / Fail:** ___

#### UAT-026 — Generate compliance email
- **Role:** NCA Admin
- **Steps:**
  1. Find a MISSING_DATA flag
  2. Click "Email Provider"
- **Expected:** Email draft shown with provider's missing field count and details
- **Pass / Fail:** ___

#### UAT-027 — Provider sees own compliance alerts
- **Role:** Provider (Data Entry)
- **Steps:**
  1. Log in as dataentry@vodafone.com.gh
  2. View provider dashboard
- **Expected:** See only Vodafone's own compliance alerts and completion percentages — no other provider data
- **Pass / Fail:** ___

---

### Module 6: Users

#### UAT-028 — Create a new user
- **Role:** NCA Admin
- **Steps:**
  1. Click "Users" in the sidebar
  2. Click "+ New User"
  3. Fill in: name, email, password (12+ chars), role = NCA Officer
  4. Click "Create User"
- **Expected:** User appears in the table, can now log in with those credentials
- **Pass / Fail:** ___

#### UAT-029 — Deactivate a user
- **Role:** NCA Admin
- **Steps:**
  1. Find any active user in the Users table
  2. Click "Deactivate"
- **Expected:** User's row shows "Inactive" badge, user cannot log in
- **Pass / Fail:** ___

#### UAT-030 — Create a Provider user with organisation
- **Role:** NCA Admin
- **Steps:**
  1. New User form → set role to "Provider Data Entry"
  2. Select an organisation from the dropdown that appears
  3. Create user
- **Expected:** User created successfully and linked to that provider organisation
- **Pass / Fail:** ___

---

### Module 7: Exports

#### UAT-031 — Export submission data as CSV
- **Role:** NCA Admin or NCA Officer
- **Steps:**
  1. Click "Exports" in the sidebar
  2. Select a provider from the dropdown
  3. Click Export
- **Expected:** CSV file downloads with columns: submission_id, provider_name, period_name, form_code, field_name, value
- **Pass / Fail:** ___

#### UAT-032 — Exported CSV contains real values
- **Role:** NCA Admin
- **Steps:**
  1. Export CSV for Vodafone
  2. Open in Excel or Google Sheets
- **Expected:** Rows contain actual submitted data values, not empty cells
- **Pass / Fail:** ___

---

### Module 8: Access Control (Security)

#### UAT-033 — Provider cannot access NCA dashboard
- **Role:** Provider (Data Entry)
- **Steps:**
  1. Log in as provider
  2. Manually try to navigate to /dashboard or /users in the browser address bar
- **Expected:** Redirected away or access denied — cannot see NCA pages
- **Pass / Fail:** ___

#### UAT-034 — Provider cannot access other provider's submission
- **Role:** Provider (Data Entry) — Vodafone
- **Steps:**
  1. Log in as Vodafone provider
  2. Note the URL of a Vodafone submission, e.g. /provider/submissions/5
  3. Change the ID to a different number that belongs to another provider
- **Expected:** 403 forbidden or "not found" — cannot access another provider's submission
- **Pass / Fail:** ___

---

## UAT Sign-Off Sheet

To be completed after UAT is done:

| Module | Total Tests | Passed | Failed | Notes |
|--------|-------------|--------|--------|-------|
| Authentication | 3 | | | |
| Dashboard | 2 | | | |
| Providers | 5 | | | |
| Submissions | 9 | | | |
| Compliance | 5 | | | |
| Users | 3 | | | |
| Exports | 2 | | | |
| Access Control | 2 | | | |
| **TOTAL** | **31** | | | |

**Tested by:** ___________________________  
**Date:** ___________________________  
**System version / URL:** ___________________________  
**Overall result:** PASS / FAIL  
**Sign-off:** ___________________________  

---

## Known Limitations During Testing

| Item | Status | Notes |
|------|--------|-------|
| Email sending (SMTP) | Not configured | Email drafts generate but are not sent |
| Celery background tasks | Not running | Compliance flags must be run manually via `python manage.py flag_missing_data` |
| Database persistence | Resets on HF restart | Data is re-seeded automatically on each container start |
| File storage | Local disk only | Uploaded Excel files are stored in-container and lost on restart |

---

## Reporting a Bug

When a test fails, record:

1. **Test ID** (e.g. UAT-018)
2. **Steps you took** (exactly)
3. **What you expected**
4. **What actually happened** (screenshot if possible)
5. **Browser and device** (e.g. Chrome on Windows 11)
6. **URL** when the error occurred

Send bug reports to the development team with this information.

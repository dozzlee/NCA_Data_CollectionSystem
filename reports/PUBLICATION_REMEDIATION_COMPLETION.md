# NCA Publication Remediation Completion Report

**Completed:** 12 August 2026
**Repository:** `C:\Users\dozzl\OneDrive\Documents\testing and fixing`
**Branch:** `testing_fix`
**Local services:** frontend `http://127.0.0.1:3001`; backend `http://127.0.0.1:8001`

## Outcome

The planned code-level publication remediation is implemented in the existing repository without a merge, reset, history rewrite or unrelated-project change. Historical submissions and templates remain attached to their original immutable versions. The five-role model, provider assignments and Data Request portal are preserved.

Publication is **not yet approved**. The mandatory external gates in `operations/RELEASE_READINESS.md` remain outstanding, and Docker is not installed on this workstation, so the Compose configuration/build and container smoke test could not be executed here.

## Delivered system

- Seven PRD-derived corrected form versions with structured Section 11 requirements, strict structural gap checks, publication gates and audited safe legacy migration.
- Explicit provider workflow, targeted correction/resubmission, immutable events/notifications and full provider isolation.
- Transactional scalar/grid snapshots with revision conflicts, fixed-row preservation, non-filled explanations, calculated values and full transition validation.
- Exact-version NCA review data, legacy coverage warnings, correction cloning/locking and approval blockers.
- Five-role capability enforcement: Officer parity except Users/divisions/Data Requests; Data Entry technical support only; Approver compliance and provider approval; requester-only governed portal.
- Aggregate Industry Dashboard for every authenticated role, with NCA-only source/update tools and aggregate XLSX export.
- Approved-only operational CSV/PDF export, private KMZ/Excel controls, scan/hash metadata and audited authenticated downloads.
- Secure HttpOnly cookie JWT authentication, CSRF, refresh rotation/blacklist, login throttling/lockout and audited Admin-mediated password reset. MFA is explicitly deferred and no fake MFA route remains.
- Production security fail-fast settings, private managed-ingress boundary, Docker services, recovery/readiness gates and updated operational documentation.
- Updated PRD copy preserving the source document and styling; 26 pages were rendered and visually inspected.
- Repeatable five-role Playwright/axe tests in addition to backend/API and build checks.

## Verification evidence

| Check | Result |
|---|---|
| Django system check | PASS — 0 issues |
| Migration drift | PASS — no changes detected |
| Migration plan | PASS — no pending operations in the local migrated database |
| Backend tests | PASS — 43/43 |
| Corrected-form loader/tests | PASS — all seven replacement versions published in test database |
| Legacy migration test | PASS — dry-run and commit paths, 0 blocked in deterministic fixture |
| Frontend ESLint | PASS — 0 warnings/errors |
| TypeScript | PASS |
| Next.js production build | PASS — Next 16.3.0, 27 routes |
| Playwright + axe | PASS — 5/5 role/accessibility scenarios |
| Production Django check | PASS — `check --deploy`, 0 issues with safe non-secret test settings |
| Python dependency audit | PASS — no known vulnerabilities; `pip check` clean |
| Frontend production audit | PASS WITH ADVISORY — 0 high/critical, 1 moderate in ExcelJS's `uuid@8.3.2` transitive dependency (GHSA-w5hq-g745-h8pq); code uses UUID generation without a caller-supplied buffer |
| Local HTTP smoke | PASS — frontend login and backend CSRF endpoints return 200 |
| DOCX render/visual QA | PASS — all 26 pages inspected; no clipping or overlap observed |
| Docker Compose config/build/smoke | NOT RUN — Docker command is not installed on this workstation |

## Release blockers and external inputs

- Install/use a Docker-capable release host and pass Compose config, image build and full container smoke tests.
- Supply the NCA production domain, strong secrets, HTTPS origins and trusted managed-ingress/private-bind configuration.
- Import and approve the official provider/form assignment register.
- Confirm or replace the provisional `TOWER-MAIN-ANNUAL` code.
- Configure immutable database/private-file backup storage and pass an isolated restore against approved RPO/RTO.
- Approve retention policies before enabling automated disposition.
- Supply approved penalty wording if correspondence will use it.
- Complete named NCA/provider, browser, assistive-technology, Excel/Google Sheets and CSV/XLSX/PDF UAT sign-off.
- Microsoft Graph/shared-mailbox delivery is advisory for this release; messages remain `DRAFT`/`QUEUED` until credentials and delivery evidence exist.

## Publication commands

Run on the approved Docker-capable release host after all blockers are cleared:

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend python manage.py check --deploy --settings=config.settings.production
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Then execute every item in `SMOKE_TEST.md`, attach restore/UAT evidence and approve the readiness view. No publication claim is valid before those checks pass.

## Exact changed-file manifest

The manifest below records the complete working-tree scope at handoff. Directory entries mean all listed files within that new directory.

### Added

- `API.md`
- `backend/apps/data_requests/migrations/0002_requester_grade_and_division_directory.py`
- `backend/apps/feedback/tests.py`
- `backend/apps/forms_engine/gaps.py`
- `backend/apps/forms_engine/management/__init__.py`
- `backend/apps/forms_engine/management/commands/__init__.py`
- `backend/apps/forms_engine/management/commands/load_prd_section11.py`
- `backend/apps/forms_engine/migrations/0005_formrequirement_formgapassessment.py`
- `backend/apps/forms_engine/migrations/0006_alter_prd_form_code_labels.py`
- `backend/apps/forms_engine/migrations/0007_form_specific_review.py`
- `backend/apps/forms_engine/migrations/0008_formfamily_code_status.py`
- `backend/apps/forms_engine/rules.py`
- `backend/apps/forms_engine/tests.py`
- `backend/apps/providers/migrations/0003_providerformassignment.py`
- `backend/apps/providers/tests.py`
- `backend/apps/submissions/industry_dashboard.py`
- `backend/apps/submissions/management/commands/migrate_legacy_forms.py`
- `backend/apps/submissions/migrations/0003_submissionevent_submissionnotification_and_more.py`
- `backend/apps/submissions/migrations/0004_expectedsubmission_migration_report_and_more.py`
- `backend/apps/submissions/workflow.py`
- `backend/apps/users/authentication.py`
- `backend/apps/users/migrations/0004_ncadivision_user_division_user_grade.py`
- `backend/apps/users/migrations/0005_user_must_change_password.py`
- `backend/apps/users/tests.py`
- `backend/config/middleware.py`
- `backend/private_dashboard/industry-dashboard.json`
- `frontend/AGENTS.md`
- `frontend/CLAUDE.md`
- `frontend/app/(auth)/change-password/page.tsx`
- `frontend/app/(nca)/forms/[id]/gaps/page.tsx`
- `frontend/app/(provider)/provider/notifications/page.tsx`
- `frontend/e2e/role-access.spec.ts`
- `frontend/eslint.config.mjs`
- `frontend/playwright.config.ts`
- `operations/RELEASE_READINESS.md`
- `reports/Product Requirements Document - Development Ready - Updated.docx`
- `reports/PUBLICATION_REMEDIATION_COMPLETION.md`
- `reports/update_prd.py`

### Deleted

- `frontend/.eslintrc.json`
- `frontend/app/(auth)/mfa/page.tsx`
- `frontend/public/data/industry-dashboard.json`

### Modified

- `.env.example`
- `DEPLOYMENT.md`
- `Dockerfile`
- `PRODUCT.md`
- `README.md`
- `SMOKE_TEST.md`
- `backend/apps/audit/views.py`
- `backend/apps/compliance/urls.py`
- `backend/apps/compliance/views.py`
- `backend/apps/data_requests/management/commands/seed_data_requests.py`
- `backend/apps/data_requests/models.py`
- `backend/apps/data_requests/serializers.py`
- `backend/apps/data_requests/tests.py`
- `backend/apps/exports/services.py`
- `backend/apps/exports/urls.py`
- `backend/apps/exports/views.py`
- `backend/apps/feedback/views.py`
- `backend/apps/forms_engine/admin.py`
- `backend/apps/forms_engine/models.py`
- `backend/apps/forms_engine/serializers.py`
- `backend/apps/forms_engine/urls.py`
- `backend/apps/forms_engine/views.py`
- `backend/apps/governance/views.py`
- `backend/apps/providers/admin.py`
- `backend/apps/providers/models.py`
- `backend/apps/providers/serializers.py`
- `backend/apps/providers/urls.py`
- `backend/apps/providers/views.py`
- `backend/apps/submissions/models.py`
- `backend/apps/submissions/readiness.py`
- `backend/apps/submissions/serializers.py`
- `backend/apps/submissions/tests.py`
- `backend/apps/submissions/urls.py`
- `backend/apps/submissions/validation.py`
- `backend/apps/submissions/views.py`
- `backend/apps/uploads/models.py`
- `backend/apps/uploads/views.py`
- `backend/apps/users/admin.py`
- `backend/apps/users/models.py`
- `backend/apps/users/permissions.py`
- `backend/apps/users/serializers.py`
- `backend/apps/users/urls.py`
- `backend/apps/users/views.py`
- `backend/config/settings/base.py`
- `backend/config/settings/development.py`
- `backend/config/settings/production.py`
- `backend/config/urls.py`
- `backend/requirements.txt`
- `docker-compose.prod.yml`
- `docker-compose.yml`
- `frontend/Dockerfile`
- `frontend/app/(auth)/login/page.tsx`
- `frontend/app/(nca)/dashboard/page.tsx`
- `frontend/app/(nca)/data-requests/new/page.tsx`
- `frontend/app/(nca)/data-requests/page.tsx`
- `frontend/app/(nca)/exports/page.tsx`
- `frontend/app/(nca)/forms/[id]/page.tsx`
- `frontend/app/(nca)/submissions/[id]/review/page.tsx`
- `frontend/app/(nca)/users/page.tsx`
- `frontend/app/(provider)/provider/compliance/page.tsx`
- `frontend/app/(provider)/provider/dashboard/page.tsx`
- `frontend/app/(provider)/provider/inquiries/page.tsx`
- `frontend/app/(provider)/provider/pending-approval/page.tsx`
- `frontend/app/(provider)/provider/submissions/[id]/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/industry-dashboard/page.tsx`
- `frontend/components/forms/FieldRenderer.tsx`
- `frontend/components/forms/GridRenderer.tsx`
- `frontend/components/industry/IndustryDashboard.tsx`
- `frontend/components/layout/ProviderTopBar.tsx`
- `frontend/components/layout/Sidebar.tsx`
- `frontend/components/layout/TopBar.tsx`
- `frontend/hooks/useFormEntry.ts`
- `frontend/hooks/useSessionTimeout.ts`
- `frontend/lib/api.ts`
- `frontend/lib/auth.ts`
- `frontend/lib/types.ts`
- `frontend/lib/utils.ts`
- `frontend/next-env.d.ts`
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `frontend/pnpm-workspace.yaml`
- `frontend/tsconfig.json`
- `nginx/nginx.conf`
- `testing/UAT_TRACEABILITY.md`

The original PRD at `C:\Users\dozzl\Downloads\Product Requirements Document - Development Ready.docx` was not overwritten.

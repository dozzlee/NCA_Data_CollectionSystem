# NCA Data Collection and Compliance Management System

This repository contains the NCA regulatory data-collection portal: a Django 5.2 API, Next.js 16 frontend, PostgreSQL, Redis/Celery, ClamAV, Nginx, private file storage and recovery tooling.

## Roles

- NCA Admin: complete access, including Users and Data Requests.
- NCA Officer: operational parity with Admin except Users, divisions and Data Requests.
- Provider Approver: works a server-calculated approval/NCA-correction queue, may edit permitted stages with immutable diffs, returns targeted corrections, attests official returns and may contact NCA.
- Provider Data Entry: shares its provider's draft/correction queue, uses optimistic autosave/manual save, sees read-only corrective compliance information and raises/tracks technical support issues.
- NCA Data Requester: metadata catalog, own requests, notifications and released files.

## Corrected forms

The active immutable PRD Section 11 versions are `MNO-MONTHLY` 3.0, `DC-ISP06` 3.0, `DC-ITC04` 3.0, `DC-TB02` 3.0, `TOWER-MAIN-ANNUAL` 2.0 (provisional code), `DC-DBS05` 2.0 and `DC-SUB03` 2.0. Topology KMZ is required only for `DC-DBS05`.

## Local verification

Use PostgreSQL and Redis from `docker-compose.yml`, then run:

```powershell
docker compose up -d db redis
cd backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

In a second terminal:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev --port 3001
```

The local UI is `http://127.0.0.1:3001`; the API is `http://127.0.0.1:8001/api/v1/`.

Demo records are never loaded automatically. For an explicitly local dataset only:

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py seed_data_requests
```

The local fixture includes representative Draft, Pending Provider Approval, Provider Changes Requested, Provider Resubmitted and NCA Correction Requested items. Production startup never invokes this command.

## Checks

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py test
cd ..\frontend
pnpm lint
pnpm exec tsc --noEmit
pnpm build
pnpm audit --prod --audit-level high
```

See [DEPLOYMENT.md](DEPLOYMENT.md), [SMOKE_TEST.md](SMOKE_TEST.md), [API.md](API.md) and [operations/RELEASE_READINESS.md](operations/RELEASE_READINESS.md).

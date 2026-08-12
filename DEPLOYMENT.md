# NCA Production Deployment

Production uses `docker-compose.prod.yml` behind an NCA-controlled managed TLS ingress. Do not publish the application directly over HTTP, run development servers, or load demo fixtures.

## Required external configuration

Copy `.env.example` to `.env` and replace every placeholder. At minimum production startup requires a strong `SECRET_KEY` and `AUDIT_HMAC_KEY`, non-local `ALLOWED_HOSTS`, HTTPS CORS/CSRF origins and portal URL, trusted proxy CIDRs, database password, and approved RPO/RTO targets. Keep retention disposition disabled until all record-class policies are approved.

Microsoft Graph/shared-mailbox credentials are optional for this release. Without them, outbound messages remain `DRAFT` or `QUEUED` and are never shown as sent.

## Validate configuration

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend python manage.py check --deploy --settings=config.settings.production
```

Production settings intentionally fail closed when security or recovery targets are missing.

## Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate --plan
```

Services are PostgreSQL, Redis, backend/Gunicorn, frontend/Next standalone, Celery worker, Celery beat, ClamAV and Nginx. pgBackRest is available through the `recovery` profile after immutable backup storage credentials and configuration are approved.

Only Nginx is host-bound, on loopback port `8080` by default. The managed ingress must terminate TLS and connect to this trusted proxy path; use `INGRESS_BIND_ADDRESS` only for a specifically assigned private interface. Backend, frontend, database, Redis and ClamAV stay private. Nginx marks this private hop as HTTPS and replaces client-supplied forwarding headers; Django accepts the protocol assertion only from configured proxy CIDRs.

## Initial administration

Apply migrations and create the first NCA Admin interactively. Load the Ghana region fixture if it is not already present. Do not run `seed_data` or `seed_data_requests` in production.

Before user access, load and verify the seven PRD-derived forms using the approved PRD copy, import confirmed provider/form assignments, create reporting periods, and run the smoke test. Historical templates and submissions must not be deleted.

## Private files and recovery

Private uploads/exports are mounted outside public media. ClamAV must report `CLEAN` before download. Back up PostgreSQL/WAL and private files to approved encrypted immutable storage. Run an isolated restore verification before release and monthly thereafter; record evidence and measured RPO/RTO in the governance module.

## Upgrade procedure

1. Confirm a successful backup and verified restore.
2. Review forward migrations with `migrate --plan`.
3. Build and run all automated checks.
4. Deploy, apply migrations and run [SMOKE_TEST.md](SMOKE_TEST.md).
5. Roll back application images only if necessary; never reverse or delete historical data without an approved migration plan.

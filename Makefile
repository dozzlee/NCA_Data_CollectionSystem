COMPOSE      = docker compose -f docker-compose.prod.yml
COMPOSE_DEV  = docker compose
BACKEND      = $(COMPOSE) exec backend
BACKUP_DIR   = ./backups

.PHONY: up down restart logs logs-backend logs-frontend logs-nginx \
        migrate seed createsuperuser refresh-due-states \
        backup restore shell-backend shell-db \
        dev dev-down build

# ── Production ────────────────────────────────────────────────────────────────

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

build:
	$(COMPOSE) up -d --build

logs:
	$(COMPOSE) logs -f --tail=100

logs-backend:
	$(COMPOSE) logs -f --tail=100 backend

logs-frontend:
	$(COMPOSE) logs -f --tail=100 frontend

logs-nginx:
	$(COMPOSE) logs -f --tail=100 nginx

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	$(BACKEND) python manage.py migrate --run-syncdb

seed:
	$(BACKEND) python manage.py loaddata fixtures/ghana_regions.json
	$(BACKEND) python manage.py loaddata fixtures/email_templates.json

createsuperuser:
	$(BACKEND) python manage.py createsuperuser

refresh-due-states:
	$(BACKEND) python manage.py refresh_due_states

# ── Backups ───────────────────────────────────────────────────────────────────

backup:
	@mkdir -p $(BACKUP_DIR)
	@TIMESTAMP=$$(date +%Y-%m-%d_%H-%M); \
	FILENAME=$(BACKUP_DIR)/nca_db_$$TIMESTAMP.sql.gz; \
	$(COMPOSE) exec -T db pg_dump -U nca nca_dc | gzip > $$FILENAME; \
	echo "Backup written to $$FILENAME"

restore:
ifndef FILE
	$(error Usage: make restore FILE=backups/nca_db_YYYY-MM-DD_HH-MM.sql.gz)
endif
	@echo "Restoring from $(FILE) — this will DROP the existing database."
	@read -p "Type 'yes' to confirm: " CONFIRM && [ "$$CONFIRM" = "yes" ]
	$(COMPOSE) exec -T db psql -U nca -c "DROP DATABASE IF EXISTS nca_dc;"
	$(COMPOSE) exec -T db psql -U nca -c "CREATE DATABASE nca_dc;"
	gunzip -c $(FILE) | $(COMPOSE) exec -T db psql -U nca nca_dc
	@echo "Restore complete."

# ── Shells ────────────────────────────────────────────────────────────────────

shell-backend:
	$(BACKEND) python manage.py shell

shell-db:
	$(COMPOSE) exec db psql -U nca nca_dc

# ── Development ───────────────────────────────────────────────────────────────

dev:
	$(COMPOSE_DEV) up -d

dev-down:
	$(COMPOSE_DEV) down

dev-migrate:
	$(COMPOSE_DEV) exec backend python manage.py migrate

dev-seed:
	$(COMPOSE_DEV) exec backend python manage.py loaddata fixtures/ghana_regions.json
	$(COMPOSE_DEV) exec backend python manage.py loaddata fixtures/email_templates.json

dev-createsuperuser:
	$(COMPOSE_DEV) exec backend python manage.py createsuperuser

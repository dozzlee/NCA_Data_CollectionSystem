#!/usr/bin/env bash
# NCA Data Collection System — automated backup script
# Intended to be run by cron. Keeps the last 30 daily backups.
#
# Crontab entry (runs at 01:00 every day):
#   0 1 * * * /opt/nca-data-collection/scripts/backup.sh >> /var/log/nca-backup.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
KEEP_DAYS=30
TIMESTAMP="$(date +%Y-%m-%d_%H-%M)"
FILENAME="$BACKUP_DIR/nca_db_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting backup..."

# Database dump (compressed)
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" exec -T db \
  pg_dump -U nca nca_dc | gzip > "$FILENAME"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Database backup written to $FILENAME ($(du -h "$FILENAME" | cut -f1))"

# Remove backups older than KEEP_DAYS
DELETED=$(find "$BACKUP_DIR" -name "nca_db_*.sql.gz" -mtime +$KEEP_DAYS -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Removed $DELETED old backup(s) (>${KEEP_DAYS}d)"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup complete."

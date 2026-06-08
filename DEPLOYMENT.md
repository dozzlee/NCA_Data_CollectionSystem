# NCA Data Collection System — Deployment Guide

**Target environment:** Ubuntu 22.04 LTS server on a local VM  
**Audience:** IT administrator performing the initial installation  
**Last updated:** 2026-06-08

---

## Prerequisites

The server needs:
- Ubuntu 22.04 LTS (desktop or server edition)
- 4 GB RAM minimum (8 GB recommended)
- 20 GB free disk space
- Internet access (for the initial Docker image pull only)
- A static IP address on the LAN (e.g. `192.168.1.100`)

---

## Step 1 — Install Docker and Docker Compose

```bash
# Remove any old Docker packages
sudo apt-get remove -y docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key and repository
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow running Docker without sudo (log out and back in after this)
sudo usermod -aG docker $USER
```

Verify the installation:

```bash
docker --version          # Docker 24.x or later
docker compose version    # Docker Compose v2.x
```

---

## Step 2 — Clone the Repository

```bash
cd /opt
sudo git clone https://github.com/dozzlee/NCA_Data_CollectionSystem.git nca-data-collection
sudo chown -R $USER:$USER nca-data-collection
cd nca-data-collection
```

---

## Step 3 — Configure Environment Variables

Copy the example file and fill in the required values:

```bash
cp .env.example .env
nano .env
```

Set these values in `.env`:

```
# Required — change both of these before starting
DB_PASSWORD=<strong-random-password>
SECRET_KEY=<generate-with-the-command-below>

# Set to your server's LAN IP (and hostname if applicable)
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100

# Email addresses for system notifications
SUPPORT_EMAIL=it@nca.org.gh
FEEDBACK_EMAIL=feedback@nca.org.gh
```

Generate a strong `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

> **Security note:** `.env` contains credentials. Never commit it to version control. The `.gitignore` already excludes it.

---

## Step 4 — Start the Application

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds all images and starts four containers:
- `db` — PostgreSQL 16
- `backend` — Django + Gunicorn
- `frontend` — Next.js (standalone)
- `nginx` — Reverse proxy on port 80

Wait ~60 seconds for all services to become healthy, then check:

```bash
docker compose -f docker-compose.prod.yml ps
```

All four services should show `Up`.

---

## Step 5 — Run Migrations and Seed Data (one-time)

These commands only need to be run once — on the initial installation.

```bash
# Apply database migrations
make migrate

# Load fixtures (Ghana regions + email templates)
make seed

# Create the first NCA Admin account
make createsuperuser
```

When prompted for the superuser, enter:
- Email (e.g. `admin@nca.org.gh`)
- Password (use something strong — this is the primary admin account)

---

## Step 6 — Verify the Installation

Open a browser on the LAN and go to `http://192.168.1.100` (replace with your server's IP).

You should see the NCA login page. Sign in with the superuser credentials you created in Step 5.

Run the smoke test checklist in `SMOKE_TEST.md` to confirm all features are working.

---

## Step 7 — Schedule the Due-State Refresh Job

The system needs to recompute submission due states daily. Set up a cron job on the host:

```bash
crontab -e
```

Add this line (runs at 01:00 every day):

```
0 1 * * * docker exec nca-data-collection-backend-1 python manage.py refresh_due_states >> /var/log/nca-due-states.log 2>&1
```

> Confirm the container name with `docker ps --format '{{.Names}}'` — it may differ slightly.

---

## Routine Operations

### Start / stop

```bash
make up        # Start all services
make down      # Stop all services (data is preserved)
```

### View logs

```bash
make logs             # All containers
make logs-backend     # Django/Gunicorn only
make logs-nginx       # Nginx access/error logs
```

### Database backup

```bash
make backup
```

Backups are written to `./backups/` as timestamped `.sql.gz` files. Run this before any upgrade.

### Restore a backup

```bash
make restore FILE=backups/nca_db_2026-06-08_01-00.sql.gz
```

### Upgrade the application

```bash
git pull origin main
make backup                                            # Always backup first
docker compose -f docker-compose.prod.yml up -d --build
make migrate
```

---

## Firewall

Open only port 80 (HTTP) to LAN clients. SSH (22) should be restricted to the administrator's machine.

```bash
sudo ufw allow from 192.168.0.0/16 to any port 80
sudo ufw allow from <admin-ip> to any port 22
sudo ufw enable
```

---

## HTTPS (Optional but Recommended)

If the server has a hostname resolvable on the LAN (e.g. via internal DNS), use Certbot with a self-signed cert or an internal CA cert placed at:

- `/etc/ssl/nca/nca.crt`
- `/etc/ssl/nca/nca.key`

Then update `nginx/nginx.conf` to add an HTTPS server block (port 443) and redirect port 80 → 443. Restart nginx:

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Blank page / 502 Bad Gateway | `make logs-nginx` — backend may still be starting |
| Login fails immediately | `make logs-backend` — check for migration errors |
| File uploads fail | Check `media_files` Docker volume is mounted; check disk space |
| Emails not sending | Verify `SUPPORT_EMAIL` in `.env`; check `make logs-backend` for SMTP errors |
| Container won't start | `docker compose -f docker-compose.prod.yml logs <service>` |

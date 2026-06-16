FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including PostgreSQL server
RUN apt-get update && apt-get install -y \
    postgresql \
    postgresql-client \
    nodejs \
    npm \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Backend setup
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Frontend setup
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci

# Copy all code
COPY backend ./backend
COPY frontend ./frontend

# Expose ports
EXPOSE 7860 8000 3000

# Startup: init postgres, run migrations, seed, start both servers
CMD bash -c "\
    service postgresql start && \
    sleep 3 && \
    su -c \"psql -c \\\"CREATE USER nca WITH PASSWORD 'nca_dev_pass';\\\"\" postgres 2>/dev/null || true && \
    su -c \"psql -c \\\"CREATE DATABASE nca_dc OWNER nca;\\\"\" postgres 2>/dev/null || true && \
    export DATABASE_URL=postgresql://nca:nca_dev_pass@localhost:5432/nca_dc && \
    cd /app/backend && \
    python manage.py migrate && \
    python manage.py seed_data && \
    python manage.py runserver 0.0.0.0:8000 & \
    cd /app/frontend && \
    NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev -- -p 7860\
"

# Compatibility image for local evaluation only. Production uses the separate
# backend/frontend images in docker-compose.prod.yml.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 libmagic1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend

EXPOSE 8000
CMD ["sh", "-c", "cd /app/backend && python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
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
EXPOSE 8000 3000

# Start both servers
CMD bash -c "cd backend && python manage.py migrate && python manage.py seed_data && python manage.py runserver 0.0.0.0:8000 & cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev"

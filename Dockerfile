# ── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS build

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy application source
COPY . .

# Persistent data directory (mount a named volume here to keep the database
# across container restarts / image upgrades)
RUN mkdir -p /data

# Default environment variables (override via docker-compose.yml or -e flags)
ENV DB_PATH=/data/jobs.db \
    SECRET_KEY=change-me-in-production \
    PORT=5000 \
    FLASK_DEBUG=0

EXPOSE 5000

# Use gunicorn with a single worker – SQLite is not safe with multiple
# concurrent writers, so one worker is the right choice here.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "app:app"]

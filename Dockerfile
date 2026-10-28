FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Pre-compile so the non-root user never needs to write to /app.
RUN python -m compileall -q /app && chmod +x /app/docker-entrypoint.sh

# Create the data directory and store the database there so it can be mounted as a volume
RUN mkdir -p /data
ENV DB_PATH=/data/jobs.db

# Set from the release tag when the image is published.
ARG APP_VERSION=""
ENV APP_VERSION=$APP_VERSION

# Mark this as a server/Docker deployment to enable multi-user and AI features.
ENV DEPLOYMENT_MODE=docker

# The app runs as this user and group (see docker-entrypoint.sh). Set them to
# your NAS user's IDs (`id` over SSH) so you can open /data in File Station.
ENV PUID=1000 PGID=1000 PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '5000'), timeout=4)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]

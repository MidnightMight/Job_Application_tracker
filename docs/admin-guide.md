# Admin Guide — Job Application Tracker

This guide covers deployment, configuration, maintenance, and multi-user setup
for administrators running their own instance of Job Application Tracker.

---

## Table of Contents

1. [First Run & Onboarding](#1-first-run--onboarding)
2. [Deployment Modes](#2-deployment-modes)
3. [Running Locally (Windows / macOS)](#3-running-locally-windows--macos)
4. [Running with Docker](#4-running-with-docker)
5. [Environment Variables](#5-environment-variables)
6. [Multi-User Setup (Docker only)](#6-multi-user-setup-docker-only)
7. [Database Maintenance](#7-database-maintenance)
8. [Updating the App](#8-updating-the-app)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. First Run & Onboarding

The first time the app starts, every page redirects to the **onboarding wizard**
(`/onboarding`). The wizard runs once and cannot be re-triggered without
resetting the database.

**Step 1 — Welcome:** Shows your deployment mode and the features available.

**Step 2 — Account & Demo Data:**

| Deployment Mode | What you see |
|---|---|
| Docker / server | Optional admin account creation + demo-data choice |
| Local (Windows / macOS) | Demo-data choice only (no login needed) |

- **Create admin account** — enter a username and password (min 8 characters).
  Login is enabled automatically. Leave all fields blank to skip (login stays
  disabled).
- **Delete sample data** — tick the checkbox to start with an empty database.
  Leave it unticked to keep the five example applications and companies.

Once the wizard is completed, `onboarding_complete` is set to `1` in the
database and the wizard never appears again.

---

## 2. Deployment Modes

The app detects its mode automatically and gates multi-user and AI features
accordingly.

| Mode | When set | Features available |
|---|---|---|
| `docker` | Running in a container, `DB_PATH` env var set, or Linux | All features including login, user management, Ollama AI |
| `local` | Windows or macOS without Docker | Single-user, no login, no AI |

**Override with an environment variable:**

```bash
DEPLOYMENT_MODE=docker python app.py   # force docker mode on any platform
DEPLOYMENT_MODE=local  python app.py   # force local mode
```

---

## 3. Running Locally (Windows / macOS)

### One-command launchers

| Platform | Command |
|---|---|
| Linux / macOS | `bash launch.sh` |
| Windows | Double-click `launch.bat` |

Both launchers automatically create a virtual environment, install dependencies,
and open the browser.

### Manual setup

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

Open <http://localhost:5000> in your browser.

---

## 4. Running with Docker

### Quick start (pre-built image)

```bash
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="change-me-in-production" \
  --name job-tracker \
  ghcr.io/midnightmight/job_application_tracker:latest
```

### Docker Compose

```bash
# Set your secret key first
export SECRET_KEY="something-long-and-random"

# Build and start
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

The database is stored in the named volume `db_data` defined in
`docker-compose.yml`. It persists across container restarts.

### Build manually

```bash
docker build -t job-application-tracker .
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="change-me-in-production" \
  job-application-tracker
```

---

## 5. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `job-tracker-secret-key-change-me` | Flask session signing key. **Change this in production.** |
| `DB_PATH` | `jobs.db` in project folder (or `/data/jobs.db` in Docker) | Path to the SQLite database |
| `PORT` | `5000` | Port the server listens on |
| `FLASK_DEBUG` | `0` | Set to `1` for debug mode (never use in production) |
| `DEPLOYMENT_MODE` | Auto-detected | Force `docker` or `local` mode |

Set variables before running:

```bash
export SECRET_KEY="something-long-and-random"
export PORT=8080
python app.py
```

---

## 6. Multi-User Setup (Docker only)

Multi-user login is only available in `docker` deployment mode.

### Enable during onboarding

On first run, the wizard prompts you to create an admin account. Fill in a
username and password — login is enabled automatically.

### Enable after onboarding

1. Go to **Settings → Users & Security**.
2. Under **Add New User**, enter a username, password (min 8 chars), and tick
   **Admin user** if appropriate.
3. Click **Add User**.
4. Toggle **Require login to access the application** to on, then click
   **Save Security Settings**.

> **Warning:** If you enable login while no users exist, the app blocks the
> change and shows an error. Always create at least one user first.

### Recovering from a lockout

If you get locked out, connect directly to the SQLite database and set
`login_enabled` to `0`:

```bash
# Docker
docker exec -it job-tracker sqlite3 /data/jobs.db \
  "UPDATE settings SET value='0' WHERE key='login_enabled';"

# Local
sqlite3 jobs.db "UPDATE settings SET value='0' WHERE key='login_enabled';"
```

---

## 7. Database Maintenance

### Backup

**Via the UI:** Go to **Export** → **Download Full Database** to download a copy
of `jobs.db`.

**Via the command line:**

```bash
# Local
cp jobs.db jobs_backup_$(date +%Y%m%d).db

# Docker
docker exec job-tracker sqlite3 /data/jobs.db ".backup /data/jobs_backup.db"
docker cp job-tracker:/data/jobs_backup.db ./jobs_backup.db
```

### Restore

Stop the server, replace `jobs.db` with your backup, and restart.

```bash
# Stop (Docker)
docker compose down

# Replace the volume file (copy from host into a temporary container)
docker run --rm -v job_tracker_data:/data -v $(pwd):/backup \
  alpine cp /backup/jobs_backup.db /data/jobs.db

# Restart
docker compose up -d
```

### Migrate to a new device

1. Export the full database via **Export → Download Full Database**.
2. Clone the repo on the new device and follow the setup steps.
3. Stop the server, replace `jobs.db` with the downloaded file, and restart.

### Reset / start fresh

To wipe all data and re-run the onboarding wizard:

```bash
# Docker — remove the volume
docker compose down
docker volume rm db_data
docker compose up -d

# Local — delete the database file
rm jobs.db
python app.py
```

---

## 8. Updating the App

### Docker (Compose)

```bash
docker compose down
git pull origin main
docker compose up --build -d
```

### Local

```bash
git pull origin main
source venv/bin/activate          # Linux / macOS
# or: venv\Scripts\activate.bat   # Windows
pip install -r requirements.txt
python app.py
```

The database schema is migrated automatically on startup — no manual SQL needed.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Blank page / redirect loop | `onboarding_complete` stuck at `0` | Set it to `1` via SQLite CLI |
| "Cannot enable login — no users exist" | Tried to enable login before adding a user | Add a user first via Settings → Users |
| Port already in use | Another process on port 5000 | Set `PORT=8081` (or any free port) |
| `SECRET_KEY` warning in logs | Default key in use | Set a strong `SECRET_KEY` env var |
| Database file locked | Multiple server instances running | Kill extra processes with `pkill -f app.py` |
| Ollama connection failed | Ollama server not running or wrong URL | Run `ollama serve`, check URL in Settings → AI |

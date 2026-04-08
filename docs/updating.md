# Updating — Job Application Tracker

This guide explains how to update the application to a newer version.
Two methods are covered: **using Git** (recommended) and **manual download**
(for environments where Git is not available or not practical).

> **Before you do anything else — back up your data.**
> Updates replace application files.  Your database is stored separately,
> but it is still good practice to export a copy before making any changes.
> See [Back up your data](#0-back-up-your-data-do-this-first) below.

---

## Table of Contents

1. [Back up your data (do this first)](#0-back-up-your-data-do-this-first)
2. [Method A — Git pull (recommended)](#method-a--git-pull-recommended)
   - [Local install](#local-install-windowsmacoslinux)
   - [Docker Compose](#docker-compose)
3. [Method B — Manual download (no Git required)](#method-b--manual-download-no-git-required)
   - [Local install](#local-install-manual)
   - [Docker — pull image from registry](#docker--pull-image-from-registry)
   - [Docker — build from downloaded source](#docker--build-from-downloaded-source)

---

## 0. Back up your data (do this first)

**Do this before any update, regardless of method.**

### Via the web UI (easiest)

1. Open the app and go to **Export**.
2. Click **Download Full Database** — this saves a copy of `jobs.db` to your
   Downloads folder.

### Via the command line

```bash
# Local install — copy the database file
cp jobs.db "jobs_backup_$(date +%Y%m%d).db"

# Docker — export from the named volume
docker exec job-tracker sqlite3 /data/jobs.db ".backup /data/jobs_backup.db"
docker cp job-tracker:/data/jobs_backup.db ./jobs_backup_$(date +%Y%m%d).db
```

Keep the backup somewhere safe before proceeding.

---

## Method A — Git pull (recommended)

### Local install (Windows / macOS / Linux)

```bash
# 1. Back up your database (see above)

# 2. Pull the latest code
git pull origin main

# 3. Activate your virtual environment
source venv/bin/activate        # Linux / macOS
# or: venv\Scripts\activate.bat # Windows

# 4. Install any new dependencies
pip install -r requirements.txt

# 5. Restart the server
python app.py
```

The database schema is migrated automatically on startup — no manual SQL needed.

### Docker Compose

```bash
# 1. Back up your database (see above)

# 2. Stop the running container (does NOT delete the data volume)
docker compose down

# 3. Pull the latest code
git pull origin main

# 4. Rebuild the image and start
docker compose up --build -d

# 5. Verify it started correctly
docker compose logs -f
```

> **Your data is safe.**  The database lives in the Docker named volume
> `db_data`.  `docker compose down` stops the container without touching the
> volume.  Only `docker compose down -v` or `docker volume rm db_data` would
> delete the volume — do not run those commands unless you intend to wipe all data.

---

## Method B — Manual download (no Git required)

Use this method if you do not have Git installed or prefer to download a
release directly from GitHub.

### Local install (manual)

1. **Back up your database** — see [section 0](#0-back-up-your-data-do-this-first).

2. **Download the latest release** from
   <https://github.com/MidnightMight/Job_Application_tracker/releases/latest>.
   Download the **Source code (zip)** or **Source code (tar.gz)** asset.

3. **Extract the archive** to a temporary folder.

4. **Copy your database to safety** before overwriting anything:
   ```bash
   cp jobs.db ~/jobs_backup_before_update.db
   ```

5. **Overwrite the application files** by copying everything from the extracted
   folder into your existing project directory.  On most systems you can simply
   replace the entire directory, **except** `jobs.db` (your database).
   ```bash
   # Example — replace all files except the database
   rsync -av --exclude='jobs.db' extracted-folder/ /path/to/project/
   ```
   On Windows, copy-paste the extracted folder contents over the existing
   folder in Explorer; choose **Replace the files in the destination** if
   prompted.  Do **not** delete `jobs.db`.

6. **Install any new dependencies**:
   ```bash
   source venv/bin/activate        # Linux / macOS
   # or: venv\Scripts\activate.bat # Windows
   pip install -r requirements.txt
   ```

7. **Restart the server**:
   ```bash
   python app.py
   ```

---

### Docker — pull image from registry

If a pre-built image is published to the GitHub Container Registry, you can
update without rebuilding locally.

> **Note:** The commands below use `job-tracker` as the container name.  If you
> started your container with a different name, substitute it accordingly.  Run
> `docker ps` to see the names of running containers.

```bash
# 1. Back up your database (see above)

# 2. Stop and remove the old container (the data volume is preserved)
docker stop job-tracker
docker rm job-tracker

# 3. Pull the latest image
docker pull ghcr.io/midnightmight/job_application_tracker:latest

# 4. Start a new container using the same data volume
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="your-secret-key-here" \
  --name job-tracker \
  ghcr.io/midnightmight/job_application_tracker:latest

# 5. Check it is running
docker logs job-tracker
```

> **Important:** `docker stop` + `docker rm` removes **only the container**,
> not the `job_tracker_data` volume that holds your database.  Do **not** run
> `docker volume rm job_tracker_data` unless you want to permanently delete all
> your data.

If you are using Docker Compose, replace steps 2–4 with:

```bash
docker compose down
docker compose pull          # pull without rebuilding
docker compose up -d
```

---

### Docker — build from downloaded source

Use this when you have downloaded the source archive and want to build the
image yourself (e.g. in an air-gapped environment).

> **Note:** The commands below use `job-tracker` as the container name.  Run
> `docker ps` to confirm the name of your running container before proceeding.

```bash
# 1. Back up your database (see above)

# 2. Download the source archive from GitHub Releases and extract it

# 3. Enter the extracted folder
cd Job_Application_tracker-x.y.z/   # adjust version number

# 4. Stop and remove the old container (data volume is preserved)
docker stop job-tracker
docker rm job-tracker

# 5. Build the new image from source
docker build -t job-application-tracker:new .

# 6. Start a new container pointing at the same data volume
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="your-secret-key-here" \
  --name job-tracker \
  job-application-tracker:new

# 7. Verify
docker logs job-tracker
```

> **Tip:** If you use a custom `docker-compose.yml`, update the `image:` line
> to match the new image tag and run `docker compose up -d`.

---

## Rolling back

If something goes wrong after an update, restore your database backup and
revert to the previous version.

### Local install

```bash
# Restore the database
cp ~/jobs_backup_before_update.db jobs.db

# Revert to the previous commit (Git method)
git checkout HEAD~1
python app.py
```

### Docker

```bash
# Stop the broken container
docker stop job-tracker && docker rm job-tracker

# Restore the database into the volume
docker run --rm \
  -v job_tracker_data:/data \
  -v $(pwd):/backup \
  alpine cp /backup/jobs_backup_before_update.db /data/jobs.db

# Start the previous image (if you tagged it before updating)
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="your-secret-key-here" \
  --name job-tracker \
  job-application-tracker:previous-tag
```

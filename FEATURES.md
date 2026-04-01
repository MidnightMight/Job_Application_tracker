# Job Application Tracker — Extended Features

This document describes the extended features added to the Job Application Tracker beyond the core CRUD and CSV-import functionality.

---

## Table of Contents

1. [Automated Reminder System](#1-automated-reminder-system)
2. [Reminder Inbox](#2-reminder-inbox)
3. [Settings Page](#3-settings-page)
4. [Export & Backup](#4-export--backup)
5. [One-Command Launcher Scripts](#5-one-command-launcher-scripts)
6. [Browser Extension Research](#6-browser-extension-research)

---

## 1. Automated Reminder System

### How It Works

A background scheduler ([APScheduler](https://apscheduler.readthedocs.io/)) runs inside the Flask server process. Every hour it checks the database for applications that:

- Have a **pending status** (Drafting_CV, Submitted, Online_Assessment, Awaiting_Response, Interview_Scheduled, Interview_In_Person, or EOI), **and**
- Have been in that status for more than the **configurable threshold** (default: **3 days**), **and**
- Do **not** already have an undismissed reminder created in the last 24 hours (to prevent duplicate notifications).

When these conditions are met, a reminder message is written to the `reminders` table and immediately appears in the Inbox.

### Configuration

The reminder threshold and on/off toggle are stored in the `settings` table and are configurable via the [Settings page](#3-settings-page).

| Setting | Default | Description |
|---|---|---|
| `reminder_enabled` | `1` (on) | Master toggle for the reminder scheduler |
| `reminder_days` | `3` | Days a pending application must wait before a reminder is created |

### Technical Details

- The scheduler uses `APScheduler`'s `BackgroundScheduler` (daemon thread — it stops automatically when the server exits).
- To avoid the double-start issue with Flask's Werkzeug reloader, the scheduler only starts when `WERKZEUG_RUN_MAIN` is not `"false"`.
- Reminders are run once on startup in addition to the hourly interval, so the inbox is populated immediately on first launch.

---

## 2. Reminder Inbox

Navigate to the **Inbox** via the bell 🔔 button in the top navigation bar.

- **Unread badge** — a red count badge appears on the Inbox button when there are unread (undismissed) reminders.
- **Message list** — each reminder shows the application company, role, current status, and how long it has been pending.
- **Dismiss individual** — click the × button on a reminder to mark it as dismissed.
- **Dismiss all** — a single button clears all reminders at once.
- Dismissed reminders remain visible in the inbox with a "Dismissed" label (they are not deleted).
- **Direct link** — each reminder includes a link to the full application detail page.

---

## 3. Settings Page

Navigate to **Settings** via the ⚙ gear icon in the navigation bar.

Currently configurable options:

| Option | Type | Description |
|---|---|---|
| Enable reminder notifications | Toggle | Turn the hourly reminder check on or off |
| Reminder threshold | Number (days) | Minimum days pending before a reminder is generated |

### Future Settings Ideas

The Settings page is designed to be extensible. Possible future additions include:

- Default status for new applications
- Email / SMTP configuration for email-based reminders
- Custom colour themes
- Auto-archive threshold (days after rejection)

---

## 4. Export & Backup

Navigate to **Export** via the ↑ export icon in the navigation bar.

### 4.1 Applications — CSV Export

Downloads all (or filtered) applications as a CSV file.

**Filter options available before export:**

| Filter | Values |
|---|---|
| Year | Any tracked year or "All years" |
| Status | Any status or "All statuses" |
| Company | Free-text substring match |

**CSV columns exported:** `id`, `company`, `job_desc`, `team`, `date_applied`, `status`, `cover_letter`, `resume`, `duration` (days), `success_chance`, `link`, `contact`, `comment`, `additional_notes`.

The filename is auto-generated based on the filters applied (e.g. `applications_2025_Submitted.csv`).

### 4.2 Company List — CSV Export

Downloads the full company tracker as a CSV file.

**CSV columns:** `id`, `company_name`, `note` (sector/industry), `applied_2023` … `applied_2027`.

Useful for sharing a curated list of companies with others, or analysing your target market in a spreadsheet tool.

### 4.3 Full Database Backup

Downloads a binary copy of the SQLite database file (`jobs.db`) as `jobs_backup.db`.

**Use cases:**

- **Migrate to a new device** — copy `jobs_backup.db` to the new installation's folder and rename it to `jobs.db`.
- **Restore from backup** — stop the server, replace `jobs.db` with the backup file, restart.
- **Point to an alternate path** — set the `DB_PATH` environment variable to the backup file's location before starting the server.

> ⚠️ The backup is a live copy made while the server is running. SQLite's WAL mode ensures consistency, but for critical backups it is safest to stop the server first.

### 4.4 Import / Restore

The Export page also surfaces the existing CSV Import feature for convenience. To restore from a database backup, follow the instructions in [4.3](#43-full-database-backup).

---

## 5. One-Command Launcher Scripts

Two launcher scripts eliminate the need to manually activate a virtual environment from the terminal for day-to-day use.

### 5.1 `launch.sh` — Linux / macOS

```bash
bash launch.sh
```

Or make it executable once and double-click it (on macOS, right-click → Open with Terminal):

```bash
chmod +x launch.sh
./launch.sh
```

**What it does:**

1. `cd`s to the script's directory.
2. Creates a `venv/` virtual environment (skipped if it already exists).
3. Activates the venv.
4. Runs `pip install -r requirements.txt` (fast no-op if nothing changed).
5. Starts `python app.py`.

### 5.2 `launch.bat` — Windows

Double-click `launch.bat` in File Explorer (or run from Command Prompt).

**What it does:**

1. Changes to the script's directory.
2. Creates `venv\` (skipped if it already exists).
3. Activates the venv.
4. Runs `pip install -r requirements.txt`.
5. Opens `http://localhost:5000` in the default browser.
6. Starts `python app.py`.
7. Pauses the window so you can read any error messages.

### Prerequisites

- **Python 3.10+** must be installed and available on `PATH`.
  - Linux/macOS: `python3`
  - Windows: `python`

---

## 6. Browser Extension Research

### Question

> *"Explore if a browser extension or some pre-existing options can do the work or not."*

The intended capability is: detect a job application portal in the browser, automatically extract key details (company, role, link), and add an entry to the tracker — without manual copy-paste.

### Findings

#### Pre-existing general-purpose tools

| Tool | What it does | Integration with this app |
|---|---|---|
| **Huntr** (huntr.me) | Full-featured job tracker browser extension (Chrome/Firefox); auto-captures LinkedIn, Indeed, etc. | ❌ — Closed platform, no export compatible with this format |
| **Teal HQ** | Similar — extension + web app | ❌ — Closed platform |
| **Job Application Tracker (Chrome Web Store)** | Simple extension, saves to extension local storage | ❌ — No link to a local Flask app |
| **Generic form-fill extensions** (e.g. Roam) | Note-taking | ❌ — Would require manual formatting |

None of the existing browser extensions integrate directly with a self-hosted Flask application.

#### Could a custom extension be built?

Yes, but it would require:

1. **A REST API endpoint** in this Flask app (e.g. `POST /api/application`) that accepts JSON.
2. A **Manifest V3 Chrome/Firefox extension** with a popup that:
   - Reads the current page title and URL.
   - Optionally tries to extract a job title using CSS selectors for common job boards (LinkedIn, Seek, Indeed, Glassdoor).
   - Sends a `POST` request to `http://localhost:5000/api/application`.

This is feasible but out of scope for this iteration. The groundwork (structured local database, existing CSV import) makes it straightforward to add in future.

#### Current best approach (no extension needed)

The existing **CSV Import** feature already handles bulk onboarding from any spreadsheet. For single-job capture:

- Copy the job URL into the **Application Link** field when adding a new application.
- Use the **"Today"** button for the date field — it takes under 30 seconds to log a new application manually.

### Recommendation

For a future browser extension integration, the recommended architecture is:

1. Add a `POST /api/applications` JSON endpoint to `app.py` (protected by an API key stored in Settings).
2. Build a minimal Manifest V3 extension that reads `location.href`, `document.title`, and optionally page-specific selectors for LinkedIn/Seek/Indeed.
3. Store the API key in the extension's options page.

This is documented here so it can be implemented in a future iteration without needing to re-research the approach.

---

*FEATURES.md — last updated 2026-04-01*

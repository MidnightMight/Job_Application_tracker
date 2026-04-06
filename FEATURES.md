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
7. [Progressive Web App (PWA)](#7-progressive-web-app-pwa)
8. [AI Server Status Indicator](#8-ai-server-status-indicator)

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

### 5.1 `launch.sh` — Linux · macOS · Unix

```bash
bash launch.sh
```

Or make it executable once and run directly (or double-click in a file manager that opens a terminal):

```bash
chmod +x launch.sh
./launch.sh
```

**Supported platforms** (detected automatically via `uname`):

| Platform | Browser auto-open | Notes |
|---|---|---|
| **Linux** (Debian, Ubuntu, Fedora, Arch …) | `xdg-open` / `gnome-open` / `kde-open` | Requires a display (`$DISPLAY` or `$WAYLAND_DISPLAY`) |
| **macOS** (Intel & Apple Silicon) | `open` (built-in) | Works out of the box |
| **FreeBSD / OpenBSD / NetBSD** | `xdg-open` / `firefox` / `chromium` | Requires a display |
| **Solaris / other Unix** | Not attempted | App still starts normally |
| **Git Bash / Cygwin / MSYS2** (Windows) | `start` | Use `launch.bat` for a better Windows experience |

**What it does, step by step:**

1. Detects the current OS with `uname`.
2. Finds a Python 3 interpreter by trying `python3`, `python3.13` … `python3.10`, `python` in order.
3. Prints a platform-specific install hint if no Python 3 is found.
4. Creates `venv/` with `python3 -m venv` (skipped if it already exists); prints a hint if `venv` is not available.
5. Activates the venv.
6. Runs `pip install -r requirements.txt` (fast no-op if nothing changed).
7. Opens `http://localhost:5000` in the default browser **in the background** (best-effort — never fatal if it fails or there is no display).
8. Starts `python app.py` in the foreground. Press **Ctrl+C** to stop.

**Respect the `PORT` environment variable:**

```bash
PORT=8080 bash launch.sh
```

The browser auto-open and the server both use `$PORT` (default `5000`).

**Prerequisites by platform:**

| Platform | Requirement | How to install |
|---|---|---|
| Ubuntu / Debian | `python3`, `python3-venv` | `sudo apt install python3 python3-venv` |
| Fedora / RHEL | `python3` | `sudo dnf install python3` |
| Arch Linux | `python` | `sudo pacman -S python` |
| macOS | Python 3.10+ | `brew install python` or [python.org](https://www.python.org/downloads/) |
| FreeBSD | `python3` | `pkg install python3` |
| OpenBSD / NetBSD | `python3` | `pkg_add python3` |

### 5.2 `launch.bat` — Windows

Double-click `launch.bat` in File Explorer, or run it from Command Prompt / PowerShell.

**What it does, step by step:**

1. Changes to the script's directory.
2. Finds a Python 3 interpreter by trying `py` (Python Launcher for Windows), then `python3`, then `python` — whichever is found first and is Python 3.
3. Prints a friendly install hint with three options if no Python 3 is found.
4. Creates `venv\` (skipped if it already exists); prints a hint if it fails.
5. Activates the venv.
6. Runs `pip install -r requirements.txt` (fast no-op if nothing changed).
7. Opens `http://localhost:%PORT%` in the default browser.
8. Starts `python app.py`. Close the window or press **Ctrl+C** to stop.

**Respect the `PORT` environment variable:**

```bat
set PORT=8080
launch.bat
```

Or set it as a system variable in Control Panel → System → Advanced → Environment Variables.

**Prerequisites:**

Python 3.10+ installed and on `PATH`. Three ways to get it:

| Method | Command / Link | Notes |
|---|---|---|
| **Microsoft Store** | Search "Python 3" in the Store | Easiest — no PATH setup needed |
| **python.org installer** | [python.org/downloads](https://www.python.org/downloads/) | Tick **"Add Python to PATH"** during install |
| **winget** | `winget install Python.Python.3` | From Command Prompt / Terminal |

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

## 7. Progressive Web App (PWA)

The tracker ships with a full PWA implementation, allowing users to install it to their home screen on Android, iOS, and desktop without any app store involvement.

### Files added

| File | Purpose |
|---|---|
| `static/manifest.json` | Web App Manifest — app name, icons, display mode, theme colour |
| `static/sw.js` | Service worker — caching strategy and offline support |
| `static/icons/icon.svg` | SVG app icon (used by modern browsers) |
| `static/icons/icon-192.png` | 192 × 192 PNG icon (required by Android / Chrome) |
| `static/icons/icon-512.png` | 512 × 512 PNG icon (required for splash screen) |

### How to install

**Android (Chrome):**
1. Open the app in Chrome at `http://localhost:5000` (or your server address).
2. Tap the three-dot menu → **Add to Home screen**.
3. Confirm — the tracker now appears as a standalone app.

**iOS (Safari):**
1. Open the app in Safari.
2. Tap the Share icon → **Add to Home Screen**.

**Desktop (Chrome / Edge):**
Click the install icon (⊕) in the address bar, or use the browser menu → **Install Job Application Tracker**.

### Caching strategy

The service worker uses two strategies:

| Request type | Strategy | Notes |
|---|---|---|
| Navigation (HTML pages) | Network-first + cache fallback | Previously visited pages load offline |
| Static assets (CSS, JS, fonts, images) | Cache-first + background update | Instant loads; cache refreshed on next visit |
| API calls (`/api/*`) | Network-only | Never cached — always live data |
| POST / PUT / DELETE | Network-only | Mutations always go to the server |

### Cache versioning

The cache is named `job-tracker-v1`. Incrementing the version string in `sw.js` causes the old cache to be deleted on the next activation, ensuring users get updated assets after a code change.

---

## 8. AI Server Status Indicator

When the Ollama AI assistant is enabled, a live server status badge is shown in two places so users know immediately whether the AI is reachable before attempting to use it.

### Where it appears

**Application Form — AI Fill panel header:**
A small badge next to the "AI Assistant" heading shows one of three states:

| Badge | Meaning |
|---|---|
| 🟡 *Checking…* (grey spinner) | Ping in progress — shown briefly on page load |
| 🟢 *Server online* (green) | Ollama is reachable at the configured URL |
| 🔴 *Server offline* (red) | Ollama could not be reached; a help link to Settings is shown below the panel |

The status is checked once on page load and again each time the panel is expanded from its collapsed state.

**Settings → AI Assistant — card header:**
The same green/red badge appears next to the "Local LLM / Ollama Integration" heading when Ollama is enabled. The check runs automatically on page load (no need to click "Test" first). The "Test" button still works and updates the badge after a manual re-check.

### API endpoint

`GET /api/ollama-status`

Returns:

```json
// Online
{"ok": true, "model": "llama3", "models": ["llama3", "mistral"]}

// Offline or disabled
{"ok": false, "error": "Server unreachable."}
```

The endpoint is protected by `@login_required` and never exposes internal server paths or OS details in error messages.

---

*FEATURES.md — last updated 2026-04-06*

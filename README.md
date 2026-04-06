# Job Application Tracker

A personal, local web application for tracking job applications, company history,
stage progression and success rates across multiple years.

---

## Licence

This project is licenced under the [MIT Licence](LICENSE).

---

## AI Usage Disclosure

This project was developed with the assistance of **GitHub Copilot** (powered by
Claude, an AI model made by Anthropic). AI assistance was used for:

- **Code generation** — the Flask routes (`app.py`), SQLite database layer
  (`database.py`), and all HTML templates were written with AI assistance.
- **Refactoring and reorganisation** — restructuring files into the correct
  `templates/` and `static/` directories, migrating the database schema, and
  normalising status naming conventions.
- **Feature implementation** — the bulk CSV import with column-mapping UI,
  application status timeline, custom status management, required-field
  validation modal, and the "Today" date button were all implemented with
  AI-generated code.
- **Documentation** — this README and the inline code comments were drafted
  with AI assistance and reviewed by the repository owner.
- **Spelling and style corrections** — Australian English spelling corrections
  (e.g. `Offer_Received`) and consistent naming conventions applied with AI
  assistance.

All AI-generated code has been reviewed by the repository owner. The project
logic, requirements, and design decisions originate from the repository owner.

---

## Features

- **Dashboard** — summary stats with Chart.js charts (status breakdown,
  applications per year, success rate trend, industry/sector keyword frequency)
- **Year views** — filterable table of every application for a given year with
  pipeline progress bar and per-year stats
- **Application detail page** — full details, known contact, status timeline
  showing days between each stage, and a dedicated additional-notes section
- **Company tracker** — cross-year applied history per company with sector grouping
- **Custom status management** — add or remove application statuses to suit your
  own workflow
- **Bulk CSV import** — upload any CSV file then map each column to an application
  field (Mouser / DigiKey-style column-mapping UI) with a preview and
  duplicate-field warning
- **Bulk operations** — select multiple rows in a year view and set status, date,
  cover letter, resume, or delete in one action; useful for post-rejection cleanup
- **Global search** — a single search bar in the navbar queries company, job title,
  team, comment, notes, and contact across all years
- **Dark / light theme** — toggle between dark and light colour schemes with the
  🌙 / ☀️ button in the navbar; preference is saved per browser
- **CRUD** — add, edit and delete applications and companies; required-field
  validation modal on submission
- **Today button** — one-click fill for every date field alongside the native
  calendar picker
- **CLI script** — `run_script.py` prints stats and exports CSV without starting
  the server
- **Status history** — every status change is recorded with a timestamp so the
  timeline is always accurate
- **Reminder inbox** — background scheduler (APScheduler) flags applications that
  have been pending longer than a configurable number of days; a bell icon with
  an unread badge sits in the navigation bar
- **Settings page** — configure the reminder threshold (default 3 days) and
  toggle reminders on/off
- **Export & backup** — download applications or the company list as CSV (with
  optional filters), or download a full copy of the SQLite database for migration
  to another device
- **One-command launchers** — `launch.sh` (Linux / macOS / Unix) and
  `launch.bat` (Windows) handle venv creation, dependency install, and server
  start in a single step
- **Progressive Web App (PWA)** — a `manifest.json` and service worker let
  users add the tracker to their home screen on Android and iOS; the app loads
  from cache when offline so previously visited pages remain accessible without
  a network connection
- **AI server status** — when Ollama is enabled, a live green/red badge in the
  AI Fill panel header and the Settings AI card shows whether the server is
  reachable before you try to use it
- **First-run onboarding** — a setup wizard on first launch lets you create an
  admin account and clear the demo data; multi-user login and AI features are
  automatically hidden on local (Windows / macOS) installs

---

## Quick Start

### 1 — Clone the Repository

```bash
git clone https://github.com/MidnightMight/Job_Application_tracker.git
cd Job_Application_tracker
```

---

### 2 — Launch the App

Pick the method that matches your operating system.

---

#### 🐧 Linux / 🍎 macOS / 🐡 Unix — `launch.sh`

```bash
bash launch.sh
```

> **Make it executable once** so you can run it directly or double-click it in
> a file manager that opens a terminal (e.g. Nautilus, Finder with a terminal app):
> ```bash
> chmod +x launch.sh
> ./launch.sh
> ```

The script automatically:
1. Detects your OS (`Linux`, `macOS`, `FreeBSD`, `OpenBSD`, `NetBSD`, `Solaris` …)
2. Finds the right Python 3 interpreter (`python3`, `python3.13` … `python3.10`, `python`)
3. Creates `venv/` if it does not exist — with a platform-specific install hint on failure
4. Activates the virtual environment
5. Installs / verifies dependencies from `requirements.txt`
6. Opens `http://localhost:5000` in your default browser (requires a display)
7. Starts the server — press **Ctrl+C** to stop

**Python not found?** Platform-specific install commands:

| Platform | Command |
|---|---|
| Ubuntu / Debian | `sudo apt install python3 python3-venv` |
| Fedora / RHEL | `sudo dnf install python3` |
| Arch Linux | `sudo pacman -S python` |
| macOS | `brew install python` or [python.org](https://www.python.org/downloads/) |
| FreeBSD | `pkg install python3` |
| OpenBSD / NetBSD | `pkg_add python3` |

---

#### 🪟 Windows — `launch.bat`

**Double-click `launch.bat`** in File Explorer, or run it from Command Prompt /
PowerShell.

The script automatically:
1. Tries `py` (Python Launcher for Windows), then `python3`, then `python`
2. Creates `venv\` if it does not exist
3. Activates the virtual environment
4. Installs / verifies dependencies from `requirements.txt`
5. Opens `http://localhost:5000` in your default browser
6. Starts the server — close the window or press **Ctrl+C** to stop

**Python not found?** Three ways to install it:

| Method | How |
|---|---|
| Microsoft Store | Search **"Python 3"** — easiest, no PATH setup needed |
| python.org installer | [python.org/downloads](https://www.python.org/downloads/) — tick **"Add Python to PATH"** |
| winget | `winget install Python.Python.3` |

---

#### ⚙️ Manual Setup (any platform)

If you prefer to manage the virtual environment yourself:

**macOS / Linux / Unix**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

**Windows (Command Prompt)**

```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

> If PowerShell blocks the activation script, run first:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

---

### 3 — Open in Your Browser

```
http://localhost:5000
```

The first run automatically creates `jobs.db` in the project folder and seeds it
with five example applications and companies so you can explore the interface
straight away.

---

### Custom Port

All launch methods respect the `PORT` environment variable (default `5000`):

**Linux / macOS / Unix**
```bash
PORT=8080 bash launch.sh
```

**Windows (Command Prompt)**
```cmd
set PORT=8080
launch.bat
```

**Manual**
```bash
PORT=8080 python app.py          # Linux / macOS
set PORT=8080 && python app.py   # Windows CMD
```

---

## Stopping the Server

Press `Ctrl + C` in the terminal / Command Prompt window where the server is running.

## Deactivating the Virtual Environment (manual setup only)

```bash
deactivate
```

---

## Reminder Inbox

A background scheduler checks for pending applications every hour. When an
application has been in a pending status (e.g. `Submitted`, `Awaiting_Response`)
for longer than the configured threshold, a reminder is added to the inbox.

- The **bell icon** in the navigation bar shows a red badge with the unread count.
- Click **Inbox** to view, follow, or dismiss reminders.
- Configure the threshold (default **3 days**) and toggle reminders on/off via
  **Settings** in the navigation bar.

See [`FEATURES.md`](FEATURES.md) for full technical details.

---

## Export & Backup

Click **Export** in the navigation bar to:

| Export | Format | Filters available |
|---|---|---|
| Applications | CSV | Year, status, company name |
| Company list | CSV | — |
| Full database | SQLite `.db` | — |

The full database download (`jobs_backup.db`) can be used to migrate to a new
device — copy the file to the new installation folder and rename it `jobs.db`.

---

## 🐳 Docker

### Pull and run the pre-built image (recommended)

```bash
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="change-me-in-production" \
  --name job-tracker \
  ghcr.io/midnightmight/job_application_tracker:latest
```

Then open `http://localhost:5000`.

Your database is stored in the `job_tracker_data` Docker volume and persists
across container restarts and image updates.

---

### Build and run locally with Docker Compose

```bash
# Set a strong secret key first
export SECRET_KEY="something-long-and-random"

# Build the image and start the container
docker compose up --build -d

# View logs
docker compose logs -f

# Stop the container
docker compose down
```

The database is stored in the `db_data` named volume defined in
`docker-compose.yml`.

---

### Build the image manually

```bash
docker build -t job-application-tracker .
docker run -d \
  -p 5000:5000 \
  -v job_tracker_data:/data \
  -e SECRET_KEY="change-me-in-production" \
  --name job-tracker \
  job-application-tracker
```

---

### Docker environment variables

| Variable      | Default                             | Purpose                         |
|---------------|-------------------------------------|---------------------------------|
| `SECRET_KEY`  | `job-tracker-secret-key-change-me`  | Flask session signing key — **change this** |
| `DB_PATH`     | `/data/jobs.db`                     | Path to the SQLite database inside the container |
| `PORT`        | `5000`                              | Port the server listens on      |
| `FLASK_DEBUG` | `0`                                 | Set to `1` to enable debug mode |

---

## Project Structure

```
Job_Application_tracker/
├── app.py                    Flask application — all routes
├── database.py               SQLite schema, migrations, seed data, query helpers
├── run_script.py             CLI stats viewer and CSV exporter
├── requirements.txt          Python dependencies (Flask, APScheduler)
├── Dockerfile                Container image definition
├── docker-compose.yml        Compose file for one-command Docker launch
├── .dockerignore             Files excluded from the Docker build context
├── launch.sh                 One-command launcher — Linux / macOS / Unix
├── launch.bat                One-command launcher — Windows
├── FEATURES.md               Extended feature documentation
├── LICENSE                   MIT Licence
├── README.md                 This file
├── docs/
│   ├── admin-guide.md        Admin setup, Docker, maintenance, multi-user, troubleshooting
│   └── user-guide.md         How to add jobs, bulk operations, search, export, AI, and more
├── templates/
│   ├── base.html             Bootstrap 5 layout, navbar (with search + theme toggle)
│   ├── dashboard.html        Main dashboard with Chart.js charts
│   ├── year_view.html        Per-year application table with bulk-action toolbar
│   ├── application_form.html Add / edit application (with validation modal)
│   ├── application_detail.html  Full detail with status timeline and notes
│   ├── search.html           Global search results page
│   ├── csv_import.html       Bulk CSV import with column-mapping UI
│   ├── status_manager.html   Add / remove custom statuses
│   ├── companies.html        Company tracker with sector chart
│   ├── company_form.html     Add / edit company
│   ├── inbox.html            Reminder inbox
│   ├── onboarding.html       First-run setup wizard
│   ├── settings.html         App settings (reminder threshold, users, AI)
│   └── export.html           Export and backup page
├── static/
│   ├── style.css             Custom styles, status-coloured badges, timeline, dark-mode overrides
│   ├── manifest.json         PWA Web App Manifest
│   ├── sw.js                 PWA service worker (caching + offline support)
│   └── icons/                PWA app icons (SVG, 192 × 192 PNG, 512 × 512 PNG)
```

---

## Bulk CSV Import

1. Click **Import CSV** in the navigation bar (or on any year-view page).
2. **Step 1 — Upload:** select your CSV file (UTF-8 or ANSI, first row must be
   column headers — any header names are fine).
3. **Step 2 — Map Columns:** a table shows every column header detected in your
   file. Use the dropdown on each row to assign it to an application field —
   exactly like the BOM upload flow on Mouser or DigiKey. Common column names
   are auto-guessed. A preview of the first five data rows is shown next to each
   column to help you confirm the mapping. A warning modal appears if you
   accidentally assign the same field to two columns.
4. Click **Import Applications** — a results page shows the count of imported
   versus skipped rows and the reason for any skipped rows.

**Required fields per row:** `company`, `date_applied`
Dates are accepted in `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY` or `MM/DD/YYYY`
format.

---

## Status Management

Navigate to **Statuses** in the navigation bar to:

- View all current statuses with their badge preview
- Add a new custom status (spaces are automatically converted to underscores)
- Delete an unused status (deletion is blocked while any application uses it)

---

## Application Status Timeline

Click the **eye icon** (or the company name) in any year view to open the full
detail page for an application. The right-hand panel shows a colour-coded timeline
of every status change with the date/time of each change and how many days elapsed
between each stage.

---

## CLI Usage

```bash
# All-year summary
python run_script.py

# Single year
python run_script.py --year 2025

# Company search
python run_script.py --company "Acme Engineering"

# Export to CSV
python run_script.py --export-csv
python run_script.py --export-csv applications_2025.csv
```

---

## Environment Variables

These are optional — sensible defaults are used if not set.

| Variable      | Default                             | Purpose                         |
|---------------|-------------------------------------|---------------------------------|
| `SECRET_KEY`  | `job-tracker-secret-key-change-me`  | Flask session signing key       |
| `DB_PATH`     | `jobs.db` (project folder)          | Path to the SQLite database     |
| `PORT`        | `5000`                              | Port the server listens on      |
| `FLASK_DEBUG` | `0`                                 | Set to `1` to enable debug mode |

Set them in your shell before running:

```bash
export SECRET_KEY="something-long-and-random"
python app.py
```

---

## Default Status Values

| Status                | Meaning                                   |
|-----------------------|-------------------------------------------|
| `Select_Status`       | Placeholder — not yet categorised         |
| `Drafting_CV`         | Preparing application materials           |
| `Submitted`           | Application submitted                     |
| `Online_Assessment`   | Online test or coding challenge received  |
| `Awaiting_Response`   | Waiting to hear back                      |
| `Interview_Scheduled` | Interview date confirmed                  |
| `Interview_In_Person` | In-person interview stage                 |
| `Offer_Received`      | Offer received                            |
| `Offer_Rejected`      | Offer declined                            |
| `Rejected`            | Application unsuccessful                  |
| `Likely_Rejected`     | No response for an extended period        |
| `Not_Applying`        | Decided not to proceed                    |
| `EOI`                 | Expression of interest submitted          |

Custom statuses can be added or removed at any time via the **Statuses** page.

---

## Documentation

The `docs/` folder contains detailed guides:

| File | Contents |
|---|---|
| [`docs/admin-guide.md`](docs/admin-guide.md) | Deployment, Docker, environment variables, multi-user setup, database maintenance, updates, and troubleshooting |
| [`docs/user-guide.md`](docs/user-guide.md) | Adding jobs, editing, bulk operations, global search, statuses, reminders, import/export, AI assistant, and theme toggle |

---

## Feasibility Notes — Future Ideas

- **Packaged executable** — tools such as PyInstaller or Nuitka can bundle the
  entire application (Python runtime included) into a single `.exe` or `.app`
  binary, making installation completely dependency-free for end users.
- **Browser extension** — a Manifest V3 extension could pre-fill the Add
  Application form by reading the job title, company and URL from job boards
  (LinkedIn, Seek, Indeed). See [`FEATURES.md`](FEATURES.md#6-browser-extension-research)
  for a full research summary and recommended architecture.
- **Email / calendar integration** — parsing interview confirmation emails and
  automatically updating the application status is technically feasible using
  the Gmail or Outlook API, though it requires OAuth setup.
- **REST API** — a JSON endpoint (`POST /api/applications`, protected by an
  API key) would enable browser-extension integration, mobile shortcuts, and
  third-party automation tools.

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
- **CRUD** — add, edit and delete applications and companies; required-field
  validation modal on submission
- **Today button** — one-click fill for every date field alongside the native
  calendar picker
- **CLI script** — `run_script.py` prints stats and exports CSV without starting
  the server
- **Status history** — every status change is recorded with a timestamp so the
  timeline is always accurate

---

## Quick Start

### 1 — Clone the Repository

```bash
git clone https://github.com/MidnightMight/Job_Application_tracker.git
cd Job_Application_tracker
```

### 2 — Create and Activate a Virtual Environment

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt)**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> If PowerShell blocks the script, run:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

You should see `(venv)` at the start of your terminal prompt once activated.

### 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs Flask — the only runtime dependency.

### 4 — Run the Application

```bash
python app.py
```

The first run automatically creates `jobs.db` in the project folder and seeds it
with five example applications and companies so you can explore the interface
straight away.

### 5 — Open in Your Browser

```
http://localhost:5000
```

---

## Stopping the Server

Press `Ctrl + C` in the terminal where the server is running.

## Deactivating the Virtual Environment

```bash
deactivate
```

---

## Project Structure

```
Job_Application_tracker/
├── app.py                    Flask application — all routes
├── database.py               SQLite schema, migrations, seed data, query helpers
├── run_script.py             CLI stats viewer and CSV exporter
├── requirements.txt          Python dependencies (Flask only)
├── LICENSE                   MIT Licence
├── README.md                 This file
├── templates/
│   ├── base.html             Bootstrap 5 layout and navigation
│   ├── dashboard.html        Main dashboard with Chart.js charts
│   ├── year_view.html        Per-year application table and pipeline bar
│   ├── application_form.html Add / edit application (with validation modal)
│   ├── application_detail.html  Full detail with status timeline and notes
│   ├── csv_import.html       Bulk CSV import with column-mapping UI
│   ├── status_manager.html   Add / remove custom statuses
│   ├── companies.html        Company tracker with sector chart
│   └── company_form.html     Add / edit company
└── static/
    └── style.css             Custom styles, status-coloured badges, timeline
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

## Feasibility Notes — Ways to Make This Easier to Use

The following improvements were considered during development and are worth
exploring in a future update:

- **One-command launcher script** — a small shell or batch script that creates
  the venv, installs dependencies and starts the server in a single step,
  removing the need to use the terminal for day-to-day use.
- **Packaged executable** — tools such as PyInstaller or Nuitka can bundle the
  entire application (Python runtime included) into a single `.exe` or `.app`
  binary, making installation completely dependency-free for end users.
- **Browser extension or bookmarklet** — a simple browser extension could
  pre-fill the Add Application form by reading the job title, company and URL
  from whatever job board the user is viewing, dramatically reducing manual data
  entry.
- **Email / calendar integration** — parsing interview confirmation emails and
  automatically updating the application status is technically feasible using
  the Gmail or Outlook API, though it requires OAuth setup.
- **Progressive Web App (PWA)** — adding a `manifest.json` and a minimal service
  worker would let users install the tracker to their home screen on mobile
  devices, giving it an app-like feel without any app store involvement.
- **Automated reminders** — a background scheduler (e.g. APScheduler) could
  send a desktop notification or email when an application has been in a pending
  status for more than a configurable number of days.

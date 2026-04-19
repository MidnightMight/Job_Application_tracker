# Job Application Tracker

A personal, local web application for tracking job applications, company history,
stage progression, and success rates across multiple years. 

[![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

### Motivation: 
I just made it cause I am bored and job application updating via excel works but it crashed too many time. Soo I built this to be free for use and open source. It will be continually improving as I go.
Update: tested with multi user and friend for feedback. feel free to give me feedback or create issue for feature suggestion or actual issue with the implemented code so far. 

---

## Licence

This project is licenced under the [MIT Licence](LICENSE).

---

## AI Usage Disclosure

Developed with the assistance of **GitHub Copilot** (Claude / GPT models).
AI assistance was used for code generation, refactoring, feature implementation,
and documentation.  All AI-generated code has been reviewed by the repository
owner.  The project logic, requirements, and design decisions originate from
the repository owner.

---

## Features

- **Dashboard** — Chart.js charts: status breakdown, applications per year,
  success rate trend, industry/sector keyword frequency; **Quick Navigation**
  card with one-click year, Company Tracker, and Import CSV links
- **Year views** — filterable per-year table with pipeline progress bar and bulk
  operations (set status, date, cover letter, resume, delete); **sort by status
  order** matching your Settings → Statuses sequence
- **Stale application detection** — applications with no status change for ≥ 3
  days (and not in a terminal state) float to the top and are highlighted in
  yellow; the threshold is shown as a hint on the application form
- **Optional Date Applied** — the Date Applied field is no longer required;
  undated applications are shown in year views and flagged stale after 3 days
- **Application archival** — applications in Rejected, Not Applying, or Job
  Expired status can be archived in one click; archived records are hidden from
  normal views but visible on the company detail page
- **Application detail** — full details, status timeline, AI fit analysis card,
  `last_modified_at`, `job_expiry_date`, and additional notes
- **Company detail** — per-company view with industry tag badges, applied-year
  summary, and all applications (active and archived) grouped by year then
  sorted by status
- **Industry / Sector tags** — comma-separated industry tags on applications and
  companies; auto-merged into the company record; shown as Bootstrap badges
- **Auto-add company** — saving an application automatically creates the company
  record if it does not already exist; syncs applied-year flags and tags on
  every subsequent update; adds an inbox reminder when a company is created
  without industry tags
- **Job advert expiry date** — record when the posting closes; a hint appears
  when you change status to "Submitted" without filling it in
- **AI fill + fit (Ollama / OpenAI / Anthropic / Custom)** — paste a job
  description to auto-fill the form and run a personalised fit analysis (score,
  matching skills, gaps, recommendation); fit prompt now incorporates your
  all-time success rate so advice is calibrated to your track record
- **Per-user AI providers** — each user can configure their own provider:
  personal Ollama server, OpenAI, Anthropic, or any OpenAI-compatible API
- **AI fit storage** — fit results are saved to the database and shown on the
  detail page; `/api/ai-fit-save` endpoint for JS-initiated saves
- **Append to Notes** — one-click button to append a formatted fit summary to
  the Additional Notes textarea
- **`last_modified_at` tracking** — timestamp updated only when a field actually
  changes (opening and closing the edit form leaves it unchanged)
- **Custom statuses** — add or remove statuses; eight core statuses are
  **protected** (🔒 badge, cannot be deleted); set custom badge background and
  text colours per status with a live-preview colour picker
- **Per-user status colour overrides** — in multi-user mode each user can
  personalise badge colours for global statuses without affecting others
- **Duplicate detection** — checks company + title + team + date; different teams
  on the same posting are treated as distinct applications
- **Bulk CSV / Excel import** — column-mapping UI with per-row preview and
  duplicate warnings
- **Global search** — queries company, role, team, comment, notes, and contact
- **Company tracker** — cross-year applied history with sector/industry tag chart;
  click any company name to open the full company detail view
- **Reminder inbox** — background scheduler flags pending applications that
  exceed a configurable threshold; inbox prompts link to company tracker when
  industry data is incomplete
- **Export** — CSV (applications, companies) or full SQLite database backup
- **Dark / light theme** — toggle persisted to `localStorage`
- **Multi-user login** — optional, Docker mode only; werkzeug password hashing;
  each user sees only their own applications, statuses, and reminders;
  `last_login_at` tracked per user
- **PWA support** — Web App Manifest + service worker for offline use

---

## Quick Start

```bash
git clone https://github.com/MidnightMight/Job_Application_tracker.git
cd Job_Application_tracker
```

| Platform | Command |
|---|---|
| 🐧 Linux / 🍎 macOS | `bash launch.sh` |
| 🪟 Windows | Double-click `launch.bat` |
| 🐳 Docker | `export SECRET_KEY="…" && docker compose up --build -d` |

Then open **http://localhost:5000** in your browser.

The first run seeds five example applications and companies so you can explore
the interface straight away.

> **Full setup instructions** (manual venv, custom port, Docker details):
> [`docs/admin-guide.md`](docs/admin-guide.md)

---

## Architecture

```
db/          Database layer — 9 focused modules (connection, init, applications,
             companies, statuses, users, settings, stats, reminders)
routes/      Flask Blueprints — 11 route modules (auth, dashboard, applications,
             import, companies, inbox, settings, api, export, onboarding, admin_db)
app.py       Thin entry point — registers blueprints, context processor, scheduler
database.py  Backward-compat shim — re-exports everything from db/
```

> Full package tree and design notes: [`docs/architecture.md`](docs/architecture.md)

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/admin-guide.md`](docs/admin-guide.md) | Deployment, Docker, env vars, multi-user, maintenance, troubleshooting |
| [`docs/updating.md`](docs/updating.md) | Update procedures — Git pull, manual download, Docker image pull, rollback |
| [`docs/user-guide.md`](docs/user-guide.md) | Adding jobs, editing, bulk ops, search, AI assistant, import/export |
| [`docs/architecture.md`](docs/architecture.md) | Package layout and design notes |
| [`docs/statuses.md`](docs/statuses.md) | Default statuses reference, protected status rules, naming convention |
| [`docs/cli.md`](docs/cli.md) | `run_script.py` command-line reference |
| [`docs/roadmap.md`](docs/roadmap.md) | Feasibility notes and future ideas |
| [`CHANGELOG.md`](CHANGELOG.md) | Full version history |
| [`FEATURES.md`](FEATURES.md) | Extended feature documentation |

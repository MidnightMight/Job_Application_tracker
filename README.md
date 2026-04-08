# Job Application Tracker

A personal, local web application for tracking job applications, company history,
stage progression, and success rates across multiple years.

[![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

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
  success rate trend, industry/sector keyword frequency
- **Year views** — filterable per-year table with pipeline progress bar and bulk
  operations (set status, date, cover letter, resume, delete)
- **Application detail** — full details, status timeline, AI fit analysis card,
  `last_modified_at`, `job_expiry_date`, and additional notes
- **Industry / Sector** — optional industry field on applications and companies;
  auto-populated on the company record when an application is saved
- **Auto-add company** — saving an application automatically creates the company
  record if it does not already exist
- **Job advert expiry date** — record when the posting closes; a hint appears
  when you change status to "Submitted" without filling it in
- **AI fill + fit (Ollama)** — paste a job description to auto-fill the form
  and run a personalised fit analysis (score, matching skills, gaps,
  recommendation) — available in both Add *and* Edit mode
- **AI fit storage** — fit results are saved to the database and shown on the
  detail page; `/api/ai-fit-save` endpoint for JS-initiated saves
- **Append to Notes** — one-click button to append a formatted fit summary to
  the Additional Notes textarea
- **`last_modified_at` tracking** — timestamp updated only when a field actually
  changes (opening and closing the edit form leaves it unchanged)
- **Custom statuses** — add or remove statuses; eight core statuses are
  **protected** (🔒 badge, cannot be deleted)
- **Duplicate detection** — checks company + title + team + date; different teams
  on the same posting are treated as distinct applications
- **Bulk CSV / Excel import** — column-mapping UI with per-row preview and
  duplicate warnings
- **Global search** — queries company, role, team, comment, notes, and contact
- **Company tracker** — cross-year applied history with sector/industry chart
- **Reminder inbox** — background scheduler flags pending applications that
  exceed a configurable threshold
- **Export** — CSV (applications, companies) or full SQLite database backup
- **Dark / light theme** — toggle persisted to `localStorage`
- **Multi-user login** — optional, Docker mode only; werkzeug password hashing
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
routes/      Flask Blueprints — 10 route modules (auth, dashboard, applications,
             import, companies, inbox, settings, api, export, onboarding)
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

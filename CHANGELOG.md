# Changelog — Job Application Tracker

All notable changes are documented here.  Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## v1.2.1 — Bug Fixes & Status Reordering

### Bug Fixes

- **Company Pool crash fixed** — enabling the Company Pool setting caused an
  HTTP 500 Internal Server Error on every visit to `/companies` due to an
  incorrect `url_for('settings', …)` call in the pool-info banner.  Fixed to
  use the correct blueprint endpoint `settings_routes.settings`.
  *(BUG-001 — see `docs/known-bugs.md`)*

### Improvements

- **Status reordering** — the status list in **Settings → Statuses** now has
  ↑/↓ buttons so users can change the display order of statuses.  The first
  status's ↑ and the last status's ↓ button are disabled automatically.
  *(BUG-002 — see `docs/known-bugs.md`)*

### Documentation

- Added `docs/known-bugs.md` — a dated log of confirmed bugs, root causes,
  fixes, and workarounds using the `YYYYMMDD` date format.

---

## v1.2.0 — Modular Refactor + AI Storage + Data Improvements

### Architecture

- **Refactored into packages** — `app.py` reduced from ~1 447 lines to ~170 lines.
  Database code split into `db/` (9 modules); routes split into `routes/` (10 Flask
  Blueprints).  `database.py` kept at the root as a backward-compat re-export shim
  so any external script using `import database as db` continues to work.

### AI Improvements

- **AI fit results now stored in DB** — `ai_fit_score`, `ai_fit_verdict`,
  `ai_matching_skills`, `ai_skill_gaps`, `ai_recommendation` columns added to
  `applications`.  Results are saved automatically via `/api/ai-fit-save` when
  analysis completes in the browser, and are also submitted as hidden form fields.
- **AI fill + fit panel in Edit mode** — the AI assistant panel is no longer
  restricted to the "Add" form; you can paste a new job description and re-run
  analysis when editing an existing application.
- **Append to Notes** — a button appears after fit analysis to append a formatted
  summary (verdict, score, matching skills, gaps, recommendation) to the Additional
  Notes textarea.

### Data Model

- **`industry` field** — optional industry/sector field on the application form;
  stored in both the `applications` and `companies` tables; auto-propagated to the
  linked company record when saving an application.
- **`job_expiry_date` field** — record the date the job advertisement closes;
  a gentle hint appears if you set status to "Submitted" without filling this in.
- **`last_modified_at` tracking** — `update_application()` compares all fields
  before saving and only updates `last_modified_at` when at least one field has
  genuinely changed, preventing spurious edits from polluting the modification log.
- **Auto-add company** — saving an application automatically creates the company
  in the Companies table if it does not already exist (using the application's
  `industry` value if provided).
- **Dynamic year navigation** — the year list in the navbar is now derived from
  actual application dates plus the current calendar year, instead of a hardcoded
  static list.

### Status Management

- **Protected statuses** — eight core statuses (`Select_Status`,
  `Drafting_Application`, `Submitted`, `Rejected`, `Offer_Received`,
  `Offer_Rejected`, `Not_Applying`, `Job_Expired`) show a 🔒 badge in Settings
  and cannot be deleted.
- **New defaults** — `Drafting_Application` and `Job_Expired` are seeded on first
  run and added automatically to existing installs on startup.

### Duplicate Detection

- **Team field included** — `find_duplicate_applications()` now considers the
  `team` field; same company + same title + same date but a **different team** is
  treated as a distinct application, not a duplicate.

### Security

- **Session-based next-URL** — `login_required` stores `request.path` in the Flask
  session (server-side) instead of a URL query parameter.  The login view only ever
  redirects to this server-stored value, eliminating the `py/url-redirection`
  open-redirect vector entirely.

### Documentation

- `README.md` trimmed to an overview and quick-start.
- New `docs/architecture.md` — package layout and design notes.
- New `docs/statuses.md` — full status reference with protected-status rules.
- New `docs/cli.md` — `run_script.py` command-line reference.
- New `docs/roadmap.md` — future ideas and feasibility notes.
- `CHANGELOG.md` (this file) extracted from `README.md`.

---

## v1.1.0 — Bulk Import, Timeline, AI Assistant

- Bulk CSV / Excel import with column-mapping UI (Mouser/DigiKey-style)
- Application status timeline on detail page (days between each stage)
- Ollama AI assistant — fill form from job description, smart fit analysis
- PDF CV upload and text extraction for profile building
- Bulk operations in year view (set status / date / cover letter / resume, delete)
- Global search across all fields
- Dark / light theme toggle (persisted to `localStorage`)
- Company pool mode (shared company list across users)
- Reminder inbox with APScheduler background checks
- PWA support (Web App Manifest + service worker)

---

## v1.0.0 — Initial Release

- Flask + SQLite application with full application CRUD
- Dashboard with Chart.js charts (status, year, success rate, sector keywords)
- Year view with filterable table
- Company tracker with cross-year history
- Custom status management
- CSV export (applications, companies, full DB backup)
- Docker support with named volume for data persistence
- Multi-user login (Docker mode only) with werkzeug password hashing
- Onboarding wizard for first-run setup

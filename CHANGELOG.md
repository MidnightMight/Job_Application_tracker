# Changelog — Job Application Tracker

All notable changes are documented here.  Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## v1.2.2 — Stale Detection, Custom Status Colours & Multi-user Scoping

### New Features

- **Quick Navigation panel** — the dashboard now shows a "Quick Navigation" card
  at the top with one-click buttons for every year view, the Company Tracker,
  and the CSV importer.

- **Stale application detection** — applications that have not had a status change
  in 3 or more days and are not in a terminal state (`Rejected`, `Offer_Received`,
  `Offer_Rejected`, `Not_Applying`, `Job_Expired`, `Select_Status`) are flagged as
  stale.  They float to the top of list views and receive a yellow left-border
  highlight (`.stale-app`) in both light and dark mode.

- **Optional `date_applied`** — the Date Applied field is no longer marked as
  required on the application form.  A help note explains that undated applications
  will be flagged stale after 3 days with no status change.  Undated records are
  included when browsing a year view.

- **Custom status badge colours** — each status in **Settings → Statuses** now has
  BG / Text colour pickers.  The chosen colours are injected as `.status-<Name>`
  CSS rules in `<head>` via the new `status_styles` global context variable.  A
  live preview badge updates as you pick colours when adding a new status.

- **Per-user status colour overrides** — in multi-user (login-enabled) mode, a
  user can set their own badge colours for any global status without affecting
  other users.  The override is stored as a separate per-user row in the
  `statuses` table.

- **`/settings/reorder-statuses` AJAX endpoint** — drag-to-reorder for statuses
  now calls a dedicated JSON endpoint (`POST /settings/reorder-statuses`) that
  saves the full order in a single request.

### Multi-user Improvements

- **`user_id` column on `applications`** — new `INTEGER` column added to the
  `applications` table (with `_add_column_if_missing` for existing databases).
  All data-access functions — `get_applications`, `search_applications`,
  `get_application`, `add_application`, `delete_application`,
  `bulk_delete_applications`, `bulk_update_applications`,
  `find_duplicate_applications` — now accept and enforce a `user_id` parameter
  when login is enabled.

- **`user_id` column on `statuses`** — `bg_color`, `text_color`, and `user_id`
  columns added to the `statuses` table.  The unique constraint is now
  `UNIQUE(name, user_id)` to allow per-user colour overrides.

- **Stats and charts scoped per user** — `get_stats`, `get_status_counts`,
  `get_apps_per_year`, `get_success_rate_per_year`, `get_company_note_frequency`,
  and `get_dynamic_years` all accept `user_id` so each user sees their own data.

- **Reminders scoped per user** — `get_pending_for_reminders`, `get_reminders`,
  `dismiss_all_reminders`, and `get_unread_reminder_count` are filtered by
  `user_id` in login-enabled mode.

- **`current_user_id()` helper** — new function in `routes/auth.py` returns the
  logged-in user's ID when login is enabled, or `None` in single-user mode
  (ensuring all-records visibility when login is disabled).

- **`is_current_user_admin()` helper** — new function in `routes/auth.py`;
  exposed as `current_is_admin` in all templates via `inject_globals`.

### Bug Fixes

- **Dashboard `current_year` hardcoded to 2025** — `current_year` on the
  dashboard is now derived from `date.today().year` instead of a hardcoded value.

- **Year view accessible without login** — `year_view` route now correctly
  applies `@login_required` (was missing in previous releases).

- **Dark mode company link visibility** — company name links in the year view
  were invisible against the dark background.  A targeted CSS rule
  (`[data-bs-theme="dark"] td.fw-semibold a`) sets an appropriate light colour.

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

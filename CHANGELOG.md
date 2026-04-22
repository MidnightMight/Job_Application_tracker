# Changelog — Job Application Tracker

All notable changes are documented here.  Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## v1.2.5 — Dashboard Attention Panel, Stall Reminders, O.t.t.o Chat, Scheduler Config

### New Features

- **Dashboard Attention Panel** — the dashboard now includes an "Attention
  Required" section that lists stalled submitted-range applications directly on
  the main page.  Each card shows the company, role, current status, and how
  long it has been inactive.  Individual entries can be snoozed for 1–72 hours
  via `POST /dashboard/attention/snooze/<app_id>` without dismissing the
  underlying reminder.

- **Stall Check-In Reminders** — a new background scheduler job
  (`_check_stale_submitted_applications`) creates `stall_checkin` inbox
  reminders for applications in the Submitted→Rejected range that have had no
  status change **and** no recorded contact for longer than the configurable
  stale threshold (default: **2 weeks**).  Both `status_changed_at` and
  `last_contact_date` are evaluated — whichever is more recent resets the stall
  clock.

- **Likely Rejected Auto-Flagging** — the same scheduler job creates
  `likely_rejected` inbox reminders and automatically lowers `success_chance`
  to ≤ 10 % for applications with no status change for longer than the
  configurable rejected threshold (default: **4 weeks**).

- **Last Contact Date field** — applications now record a `last_contact_date`
  (recruiter call, follow-up email, etc.).  The field appears on the Add/Edit
  form and detail page.  It can also be set in bulk via the year-view
  "Set Last Contact" bulk action.  Stall detection uses `max(status_changed_at,
  last_contact_date)` so logging a contact resets the check-in clock.

- **O.t.t.o AI Assistant Chat** — a dedicated `/assistant` page provides a
  conversational interface with O.t.t.o (**O**rganised **t**racking &
  **t**arget **o**pportunity).  Ask questions about your applications,
  get job-hunt advice, and plan next steps.  Available whenever at least one AI
  provider (admin Ollama or personal provider) is configured.  Route:
  `GET /assistant`; AJAX endpoint: `POST /api/assistant-chat`.

- **Configurable Scheduler Check Interval** — Settings → General now exposes a
  "Check Interval" dropdown (1 h, 6 h, 12 h, 1 d, 2 d, 3 d, 7 d) that controls
  how often the background reminder and stale-check jobs run.  The new interval
  is applied **immediately** to the running scheduler via `_reschedule_jobs()`
  without requiring a server restart.

- **Stale / Rejected Threshold Settings** — Settings → General now has two
  configurable thresholds:
  - *Stale Application* (`stale_threshold_value` + `stale_threshold_unit`,
    default 2 weeks) — triggers the stall check-in reminder.
  - *Likely Rejected* (`rejected_threshold_value` + `rejected_threshold_unit`,
    default 4 weeks) — triggers the auto-flag and success-chance reduction.
  Both accept a numeric value and a unit (days / weeks).

- **Default Sort Order Setting** — Settings → General has an "Applications
  Default Sort" preference (Date Applied or Status Order).  Previously the
  year-view defaulted to Status Order unconditionally; now users can set either
  as their default and still override it per-visit with the Sort dropdown.

- **Clear Dismissed Reminders** — the Inbox now has a "Clear dismissed" button
  (`POST /inbox/clear-dismissed`) that permanently deletes dismissed reminders
  from the database, keeping the inbox tidy.

- **O.t.t.o Onboarding Persona** — the first-run setup wizard now features
  O.t.t.o as a named guide, consistent with the AI assistant persona used
  throughout the app.

### Bug Fixes

- **Hardened Snooze Hour Parsing** — `snooze_reminder()` and
  `set_attention_snooze()` previously raised `TypeError` / `ValueError` when
  called with non-integer input (e.g. from a malformed form POST).  A new
  `_safe_snooze_hours()` helper validates and clamps the value to 0–72 hours,
  returning a safe default on any parse failure.

- **Onboarding Message Formatting** — a stray `<br>` tag inside the sample-data
  tip paragraph was removed, fixing the layout of the onboarding wizard notice.

---

## v1.2.4 — Company Detail View, Application Archival, Success-Rate AI, Status Sorting

### New Features

- **Company Detail View** — clicking a company name in the Company Tracker opens
  a dedicated `/company/<id>` detail page showing:
  - Industry tags, sector notes, and applied-year badges (each badge links to the
    year view for that year).
  - Summary counts: total / active / archived / offers for this company.
  - All applications grouped by year (newest first) then sorted by status order.
  - Active applications in a full table with stale detection, edit, archive
    actions, and a link to the detail page.
  - Archived applications shown in a separate sub-table beneath each year group
    with the archived date visible.

- **Application Archival** — applications in `Rejected`, `Not_Applying`, or
  `Job_Expired` status can now be archived with a single click.  Archived
  applications are hidden from the normal year view and search results but
  remain visible on the Company Detail page.  New schema columns `archived`
  (INTEGER DEFAULT 0) and `archived_at` (TEXT) added via auto-migration.

- **Success Rate in AI Fit Analysis** — the AI fit prompt now receives the
  user's all-time job-search track record (total submitted, offers received,
  and success rate percentage).  The AI uses this to contextualise its
  recommendation — e.g. highlighting whether a role is a realistic match or
  a stretch goal relative to the user's current success rate.

- **Year View — Sort by Status Order** — the year view now has a **Sort** dropdown
  (Date Applied / Status Order).  Status Order sorts rows according to the
  sequence configured in Settings → Statuses so similar statuses are grouped
  together visually.

- **Per-User Personal Ollama Server** — users can now configure their own Ollama
  server URL and model under Settings → AI Assistant → Personal Provider.
  Previously, personal providers were limited to cloud APIs; the local Ollama
  option is now available per-user as well.

- **Multi-Industry Tags for Companies** — the industry/sector field now stores
  comma-separated, normalised tags (duplicates removed).  Tags are shown as
  Bootstrap badges in the company list and company detail pages.  The field
  auto-merges tags from applications into the company record.

- **Last Login Tracking** — a `last_login_at` column is added to the `users`
  table (auto-migrated).  The timestamp is updated every time a user logs in or
  completes first-time password setup.  It is displayed in the Settings → Users
  & Security table.

- **Inbox Prompt for Missing Company Industry** — when an application auto-adds
  a new company without any industry tags, an inbox reminder is created that
  links directly to the Company Tracker to complete the record.

### Bug Fixes

- **Company Sync on Status/Date Changes** — updating an application's status or
  date now correctly syncs the company tracker (applies the appropriate
  `applied_<year>` flag).  Previously only the initial add triggered this sync.

- **Pipeline Progress Bar** — the year-view pipeline progress bar now renders
  one segment per status using real counts and the configured status colours
  instead of a generic "Other" bucket.

### UI Improvements

- Profile settings section (Settings → AI → Your Profile) greys out when no
  AI server is usable, re-enabling automatically when a valid admin server or
  personal provider is configured.
- Right-side toggle label removed from the personal AI provider slider.
- CV/Resume upload box now respects dark mode correctly.

---

## v1.2.3 — Admin DB Viewer, Per-User AI Providers, First-Time Login Onboarding

### New Features

- **Admin Database Viewer** — admins now have a dedicated `/admin/db` section
  accessible from **Settings → Database** (admin + Docker mode only).  Features:
  - Table overview with row counts for all 8 system tables.
  - Paginated row viewer (50 rows/page) with truncated cell previews.
  - Row edit form — change any field except primary keys; sensitive fields
    (password hashes, API keys) are always masked and can only be replaced,
    not revealed.
  - Read-only SQL console — execute `SELECT` and `PRAGMA` statements against
    the live database; results capped at 500 rows; sensitive columns masked.
  - One-click snippet buttons for common diagnostic queries.
  - Inline debug tips for the most common support scenarios.

- **Per-User AI Provider Settings** — each user can now configure their own AI
  provider independently of the shared Ollama server.  Supported providers:
  - 🦙 **Ollama** (shared admin server — default behaviour)
  - 🌐 **OpenAI** (API key + model, default `gpt-4o-mini`)
  - 🟠 **Anthropic / Claude** (API key + model, default `claude-3-haiku-20240307`)
  - 🔧 **Custom OpenAI-compatible API** (base URL + optional key, e.g. LM Studio,
    vLLM, Groq)

  Provider configuration, API keys, and user profile (skills / experience /
  summary) are all stored in a new `user_ai_settings` table — one row per user.
  In single-user (login-disabled) mode the app falls back to the existing global
  settings table so existing behaviour is unchanged.

- **Per-User Profile Storage** — skills, prior experience, and professional
  summary are now stored per-user rather than globally.  The PDF résumé upload
  also saves to the calling user's row.

- **AI Offline Overlay** — when the AI server is unreachable the AI fill panel
  on the application form collapses automatically.  If the user expands the panel
  a grey blocking overlay (unclickable) appears with:
  - "AI Server is not online" heading.
  - "Ask admin to reconfigure" button → Settings → AI.
  - "Add your own API link" button → Settings → AI → personal provider.

- **First-Time Login Password Setup** — admins can now add users without
  supplying a password.  On first login the user leaves the password field blank
  and is redirected to a dedicated `/setup-password` page where they create their
  own password (≥ 8 characters, with live match feedback).

### Improvements

- `/api/ollama-status` now returns a `provider` field so the front end can
  display the correct provider name in the AI panel badge.
- Anthropic connectivity check now actually issues a `/v1/models` request rather
  than trusting key presence alone.
- `RuntimeError` messages returned to the client are capped at 200 characters
  to avoid leaking internal details.

### Security Fixes

- SQL column names in `user_ai_settings` upserts now use a pre-built
  `_COL_UPDATES` dict instead of f-string interpolation, eliminating a potential
  SQL-injection vector.

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

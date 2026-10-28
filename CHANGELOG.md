# Changelog — Job Application Tracker

All notable changes are documented here.  Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## Unreleased

### Fixes

- **Version number**: release images now take their version from the release
  tag, so Settings shows the right version and stops offering an update to
  the version you're already on.  (v1.3.5 still reports itself as 1.3.0.)
- **Dark mode**: the boxes in the year view's bulk-edit bar showed white text
  on a white background.
- **Restore archived applications**: archived applications can now be brought
  back with **Restore** on the application page, the company page, or the year
  view's new **Archived** list (Show → Archived).  Auto-archive leaves a
  restored application alone for the set number of days.

---

## v1.3.5 — Security, Workforce Report, New Look and Insights

### Security and Deployment

- **CSRF protection** on every form and AJAX request (Flask-WTF).  Tokens last
  for the whole session; an expired form shows "The form had expired" instead
  of an error page.
- **Gunicorn** replaces the Flask development server in the Docker image (one
  worker, 4 threads, so the reminder jobs still run once).
- **Generated secret key** — `SECRET_KEY` is now optional.  If it isn't set, a
  random key is created once and saved as `secret_key` next to the database
  (`/data/secret_key` in Docker).  An existing `SECRET_KEY` still wins.
  Local installs that relied on the old built-in default get a new key, so
  log in once more.
- **Non-root container** — the app runs as `PUID:PGID` (default `1000:1000`).
  On start the container takes ownership of the data folder, so databases
  written by older (root) images stay writable.
- **Health check** — `GET /healthz` (no login) returns `{"status": "ok"}` or
  HTTP 503 if the database can't be read; the image's `HEALTHCHECK` uses it.
- **Tests on every pull request** — new *Tests* workflow runs the suite and a
  Docker smoke test (non-root user, data ownership, health check).

### Workforce Australia Report

- **How Applied** and **Employer Contact** fields on applications (form,
  detail page, CSV export and import).  Added automatically on start-up; the
  existing *Known Contact / Connection* field is unchanged.
- **Report** page (`/report/workforce`): applications applied for in one
  fortnight, lined up with the reporting period start date you save (per
  user).  Rows missing how-applied or employer-contact details are flagged.
  Per-row **Copy**, **Copy all** (tab-separated) and **Download CSV**; copying
  also works over plain `http://`.

### Next steps, insights and attachments

- **Next steps** — give an application a next step and date (follow up,
  interview, assessment due).  The dashboard's new **Coming up** list shows
  those due in the next two weeks and any overdue; the inbox gets a reminder
  on the due date.
- **Calendar feed** — Settings → General makes a private `.ics` link to
  subscribe to in any calendar app; each next step is an all-day event.
- **Share from your phone** — on Android, an installed tracker appears in the
  share menu; sharing a job ad opens the Add form with the link filled in, and
  warns if that link is already saved.
- **Saved job ad** — keep the ad text with the application (AI fill saves the
  pasted ad automatically).
- **Attachments** — attach the CV and cover letter you sent (PDF, Word, ODT,
  RTF, text; up to 10 MB) on the detail page.  Stored in `/data/attachments`.
- **Smarter duplicate warning** — also catches the same company and role
  within 60 days and the same job ad link (archived applications included),
  and says why.
- **Insights** page — heard-back and interview rates, and typical reply time,
  by how you applied and by industry.
- **Auto-archive** — optionally archive Rejected / Not Applying / Job Expired
  applications a set number of days after their last status change.
- CSV export and import include the next step, next step date and saved job ad.
- Fix: deleting an application with no date applied no longer gives an error page.

### New look (Midnight Lite)

- **New logo:** the Midnight Lite honeycomb (three amber hexagons around a blue
  one) with a briefcase in the middle.  Used in the top bar, the browser tab,
  the sign-in page and the home-screen app icon.
- **Midnight Lite colours and type:** amber and royal blue, League Spartan headings
  and Inter text, matching midnight-lite.com.  Dark mode uses the same midnight
  navy and now follows your device setting until you pick a theme.
- **Tidier top bar:** Dashboard, Applications, Companies and Report, with search,
  the inbox bell and **Add application** on the right.  Import, Export, Settings,
  the theme switch and Log out are in the menu at the top right.
- **Dashboard:** a honeycomb with one cell per status and its count this year
  (click a cell to open that list), four headline numbers, the applications in
  progress, and smaller charts in the theme colours.  The keyword chart shows a
  hint instead of an empty box when there is nothing to show.
- **Year view:** filter and sort sit on the table and apply straight away; the
  bulk-edit bar only appears once you tick a row and stays in view while you
  scroll; phones show company, role, status and days only.
- **Status names read as words** everywhere ("No status" instead of
  `Select_Status`), with one colour family per stage.  Colours set in Settings →
  Statuses still win.
- **Press /** anywhere to jump to the search box.

### Fixes

- **Search no longer crashes** when a matching application has no date applied.
- **Year view Archive and Delete buttons work again.** They sat inside the bulk-action form, so clicking one did nothing.
- **Missing pages return "404 Not Found"** instead of "500 Internal Server Error" (and no longer fill the log with stack traces).
- **No more service-worker error** in the browser console on every page (Docker mode).
- **Logout is now a button that posts a form**, so another site can't log you out with a link.

### After updating (Docker / NAS)

- Set `PUID` / `PGID` to your NAS user's IDs (optional, default `1000`).
- Keep `SECRET_KEY` if you already set one, or remove it to use a generated key
  (everyone logs in again once).

---

## v1.3.0 — Import Upgrades and Code Tidy-up

### New Features

- **Update existing applications on import** — a new tick-box on the Map
  Columns step lets an import update applications instead of skipping them.
  Rows are matched by `id` (as written by the CSV export) or by company + role
  + team + date.  Only mapped columns change, and status changes are added to
  the timeline.  Export → edit in Excel → re-import now round-trips cleanly.
- **Date Applied is optional on import** — undated rows import as undated,
  matching the add/edit form.
- **Job advert expiry date** can now be imported.
- **Import results** show rows updated, and list values that were corrected
  (unreadable dates, unknown statuses) separately from skipped rows.
- **Update notifications** — the app checks GitHub for a new release once a day
  and shows a green **Update vX.Y.Z** button in the navbar when one exists.
  Settings → Updates shows the latest release and when it was checked.
- **Docker image publishing** — a GitHub Actions workflow builds and pushes
  `ghcr.io/midnightmight/job_application_tracker` (`latest` + version tag,
  amd64 and arm64) whenever a release is published, so NAS / Container Manager
  installs have a new image to pull.

### Fixes

- The update check never reported updates for release tags like `V1.2.4A`
  (capital V and letter suffix could not be parsed).  Tags are now compared
  leniently.
- Import treated the text `0` in `cover_letter` / `resume` as "yes"; yes/no
  columns now accept `1/0`, `yes/no`, `true/false`, `y/n` and `x`.
- Unreadable dates were stored as-is; they are now left blank with a warning.
- Unknown statuses fall back to `Select_Status` with a warning instead of
  creating an orphaned status value.
- Undated duplicates were not detected on import.
- Column auto-guessing prefers exact header matches and never suggests the same
  field twice, so a re-imported export maps correctly with no manual changes.
- Background reminder jobs now log errors instead of silently swallowing them.

### Code tidy-up

- Inline JavaScript moved out of `application_form.html` and `settings.html`
  into `static/js/` (`application_form.js`, `application_ai_fill.js`,
  `application_ai_fit.js`, `settings.js`, `settings_statuses.js`).  Templates
  pass URLs and flags through a small `window.*_CONFIG` object.  Script URLs
  carry `?v=<app version>` so the service worker never serves stale copies.
- Removed the `database.py` compatibility shim; `run_script.py` now imports
  the `db` package directly.
- Added a pytest suite (`tests/`) covering import behaviour, page rendering and
  the import flow end to end.
- New `JOB_TRACKER_DISABLE_SCHEDULER=1` environment variable to run without
  the background scheduler (used by tests).

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

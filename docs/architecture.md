# Architecture — Job Application Tracker

## Package Layout

```
Job_Application_tracker/
├── app.py                    Thin Flask entry point — creates app, registers blueprints,
│                             context processor, two APScheduler background tasks
│                             (_check_and_create_reminders, _check_stale_submitted_applications)
├── database.py               Backward-compat shim — re-exports everything from db/
├── run_script.py             CLI stats viewer and CSV exporter
├── requirements.txt          Python dependencies (Flask, APScheduler, openpyxl, pypdf)
├── Dockerfile                Container image definition
├── docker-compose.yml        Compose file for one-command Docker launch
├── .dockerignore             Files excluded from the Docker build context
├── launch.sh                 One-command launcher — Linux / macOS / Unix
├── launch.bat                One-command launcher — Windows
├── FEATURES.md               Extended feature notes and future ideas
├── CHANGELOG.md              Version history
├── LICENSE                   MIT Licence
│
├── db/                       Database layer — split by concern
│   ├── __init__.py           Re-exports all public symbols (backward-compat)
│   ├── connection.py         get_connection(), DB_PATH, column-migration helper
│   ├── init_db.py            init_db(), schema creation, migrations, seed data
│   ├── applications.py       Application CRUD, duplicate detection (incl. team),
│   │                         bulk import/delete, AI fit save, last_contact_date
│   ├── companies.py          Company CRUD, auto-add-from-application
│   ├── statuses.py           get_status_options(), PROTECTED_STATUSES,
│   │                         add_status(), delete_status()
│   ├── users.py              User management (add, delete, authenticate)
│   ├── settings.py           get_setting(), set_setting(), get_all_settings()
│   ├── stats.py              Stats aggregation, get_dynamic_years()
│   └── reminders.py          Inbox / reminder helpers, stall detection,
│                             attention snooze (attention_snoozes table)
│
├── routes/                   Flask Blueprints — one per area of the app
│   ├── __init__.py
│   ├── auth.py               login_required decorator, /login, /logout,
│   │                         /setup-password, current_user_id(), is_current_user_admin()
│   ├── dashboard.py          /, /search, /year/<year>,
│   │                         /dashboard/attention/snooze/<app_id>, /assistant
│   ├── applications.py       /application/add|edit|delete|<id>, /bulk-action
│   ├── import_.py            /application/import (CSV + Excel column-mapping)
│   ├── companies.py          /companies, /company/<id>|add|edit|delete, /bulk-delete
│   ├── inbox.py              /inbox, /inbox/dismiss, /inbox/snooze,
│   │                         /inbox/dismiss-all, /inbox/clear-dismissed
│   ├── settings_routes.py    /settings, /settings/reorder-statuses,
│   │                         /settings/ollama-test, /check-update
│   ├── api.py                /api/ai-fill, /api/ai-fit, /api/ai-fit-save,
│   │                         /api/ollama-status, /api/upload-profile-pdf,
│   │                         /api/assistant-chat
│   ├── export.py             /export, /export/applications|companies|db
│   ├── admin_db.py           /admin/db — admin table viewer and SQL console
│   └── onboarding.py         /onboarding, /onboarding/user (first-run wizard)
│
├── docs/                     Detailed documentation
│   ├── admin-guide.md        Deployment, Docker, env vars, multi-user, maintenance
│   ├── user-guide.md         Adding jobs, editing, bulk ops, attention panel,
│   │                         reminders, AI fill+fit, O.t.t.o chat, import/export
│   ├── architecture.md       This file — package layout and design notes
│   ├── statuses.md           Default statuses reference and protected status rules
│   ├── cli.md                Command-line interface (run_script.py) reference
│   ├── known-bugs.md         Dated log of confirmed bugs and fixes
│   └── roadmap.md            Feasibility notes and future ideas
│
├── templates/                Jinja2 HTML templates (Bootstrap 5)
│   ├── base.html             Layout, navbar (search + theme toggle), footer
│   ├── dashboard.html        Charts (Chart.js), summary cards, attention panel,
│   │                         pending table
│   ├── year_view.html        Per-year table, bulk-action toolbar, filter bar
│   ├── application_form.html Add / edit form — AI fill+fit panel, industry,
│   │                         last_contact_date, job expiry date, validation modal
│   ├── application_detail.html  Full detail — timeline, AI fit card,
│   │                         last_modified_at, last_contact_date, notes
│   ├── assistant_chat.html   O.t.t.o conversational AI chat interface
│   ├── search.html           Global search results
│   ├── companies.html        Company tracker — sector chart, pooled view
│   ├── company_detail.html   Per-company detail — industry badges, year groups
│   ├── company_form.html     Add / edit company (with industry field)
│   ├── inbox.html            Reminder inbox
│   ├── onboarding.html       First-run setup wizard (O.t.t.o persona)
│   ├── user_onboarding.html  Per-user first-login onboarding
│   ├── settings.html         Settings — general, statuses, users, AI
│   ├── admin_db.html         Admin DB viewer — table browser and SQL console
│   ├── export.html           Export and backup
│   └── login.html            Login page
│
└── static/
    ├── style.css             Custom styles, status badges, dark-mode overrides
    ├── manifest.json         PWA Web App Manifest
    ├── sw.js                 PWA service worker
    └── icons/                PWA app icons
```

---

## Design Principles

### Backward compatibility
`database.py` at the root is kept as a shim — it does nothing except
`from db import *`.  Any external script that uses `import database as db` will
continue to work without modification.

### Blueprint registration
`app.py` creates the Flask application instance, stores `DEPLOYMENT_MODE` and
`APP_VERSION` in `app.config`, then registers all eleven route Blueprints.
The `inject_globals` context processor (also in `app.py`) injects
`ollama_enabled`, `ai_fit_enabled`, `ai_available`, `user_profile_complete`,
`years`, `unread_reminder_count`, `status_styles`, `deployment_mode`, and other
globals into every template.

### Background scheduler
`app.py` starts an `APScheduler.BackgroundScheduler` with two jobs that run on
the configured interval (`check_interval` setting, default 1 h):

| Job ID | Function | Purpose |
|---|---|---|
| `reminders` | `_check_and_create_reminders` | General pending-application reminder after N days |
| `stale_check` | `_check_stale_submitted_applications` | Stall check-in reminder + likely-rejected auto-flag |

Both jobs also run once at startup.  The interval can be changed in
Settings → General and takes effect immediately via `_reschedule_jobs()` (no
server restart needed).

### Database migrations
`db/init_db.py` calls `_add_column_if_missing()` (in `db/connection.py`) for
every column that was added after the initial schema.  The helper validates
table name, column name, and definition against explicit allowlists before
interpolating them into SQL, preventing SQL-injection via this code path.

### Dynamic year list
`db/stats.py:get_dynamic_years()` queries `strftime('%Y', date_applied)` across
all applications, unions the result with the current calendar year, and returns
a sorted list.  This replaces the old static `YEARS = [2023…2027]` constant.

### Protected statuses
Eight core statuses are listed in `db/statuses.py:PROTECTED_STATUSES`.
`delete_status()` rejects any attempt to delete them.  The Settings → Statuses
page disables the delete button and shows a 🔒 badge for each protected entry.
New protected statuses (`Drafting_Application`, `Job_Expired`) are added to
existing installs automatically by `init_db()`.

### Duplicate detection
`_dup_key(company, job_desc, team, date_applied)` is the canonical deduplication
key.  Including `team` means that the same role advertised for two different
teams on the same date is treated as two distinct applications — not a duplicate.

### Auto-add company
`db/applications.py:add_application()` runs a case-insensitive lookup after
inserting the application.  If no matching company exists it creates one,
pre-filling the `industry` column from the application's own `industry` field.

### Session-based next-URL after login
`routes/auth.py:login_required` stores `request.path` in `session["login_next"]`
(a server-side value).  The login view pops this key and validates it before
redirecting — no user-controlled data ever flows to `redirect()`, eliminating
the `py/url-redirection` CodeQL alert class entirely.

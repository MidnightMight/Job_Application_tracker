# Architecture — Job Application Tracker

## Package Layout

```
Job_Application_tracker/
├── app.py                    Thin Flask entry point — creates app, registers blueprints,
│                             context processor, APScheduler background tasks
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
│   │                         bulk import/delete, AI fit save
│   ├── companies.py          Company CRUD, auto-add-from-application
│   ├── statuses.py           get_status_options(), PROTECTED_STATUSES,
│   │                         add_status(), delete_status()
│   ├── users.py              User management (add, delete, authenticate)
│   ├── settings.py           get_setting(), set_setting(), get_all_settings()
│   ├── stats.py              Stats aggregation, get_dynamic_years()
│   └── reminders.py          Inbox / reminder helpers
│
├── routes/                   Flask Blueprints — one per area of the app
│   ├── __init__.py
│   ├── auth.py               login_required decorator, /login, /logout
│   ├── dashboard.py          /, /search, /year/<year>
│   ├── applications.py       /application/add|edit|delete|<id>, /bulk-action
│   ├── import_.py            /application/import (CSV + Excel column-mapping)
│   ├── companies.py          /companies, /company/add|edit|delete, /bulk-delete
│   ├── inbox.py              /inbox, /inbox/dismiss, /inbox/dismiss-all
│   ├── settings_routes.py    /settings, /settings/ollama-test, /check-update
│   ├── api.py                /api/ai-fill, /api/ai-fit, /api/ai-fit-save,
│   │                         /api/ollama-status, /api/upload-profile-pdf
│   ├── export.py             /export, /export/applications|companies|db
│   └── onboarding.py         /onboarding (first-run wizard)
│
├── docs/                     Detailed documentation
│   ├── admin-guide.md        Deployment, Docker, env vars, multi-user, maintenance
│   ├── user-guide.md         Adding jobs, editing, bulk ops, AI, import/export
│   ├── architecture.md       This file — package layout and design notes
│   ├── statuses.md           Default statuses reference and protected status rules
│   ├── cli.md                Command-line interface (run_script.py) reference
│   └── roadmap.md            Feasibility notes and future ideas
│
├── templates/                Jinja2 HTML templates (Bootstrap 5)
│   ├── base.html             Layout, navbar (search + theme toggle), footer
│   ├── dashboard.html        Charts (Chart.js), summary cards, pending table
│   ├── year_view.html        Per-year table, bulk-action toolbar, filter bar
│   ├── application_form.html Add / edit form — AI fill+fit panel, industry,
│   │                         job expiry date, validation modal
│   ├── application_detail.html  Full detail — timeline, AI fit card,
│   │                         last_modified_at, job_expiry_date, notes
│   ├── search.html           Global search results
│   ├── companies.html        Company tracker — sector chart, pooled view
│   ├── company_form.html     Add / edit company (with industry field)
│   ├── inbox.html            Reminder inbox
│   ├── onboarding.html       First-run setup wizard
│   ├── settings.html         Settings — general, statuses (with 🔒 lock), users, AI
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
`APP_VERSION` in `app.config`, then registers all ten route Blueprints.
The `inject_globals` context processor (also in `app.py`) injects
`ollama_enabled`, `ai_fit_enabled`, `user_profile_complete`, `years`,
`unread_reminder_count`, and other globals into every template.

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

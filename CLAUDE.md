# CLAUDE.md — Job Application Tracker

Flask + SQLite job application tracker (Python 3.12). Self-hosted in Docker on
a Synology NAS (Container Manager) from
`ghcr.io/midnightmight/job_application_tracker:latest`. Version is
`APP_VERSION` in `app.py`.

## Branches and releases

- `dev` is the integration branch. Do feature work on a branch off `dev` and
  open the PR against `dev`.
- `main` is what gets released. `dev` is merged into `main` by the owner when
  a version is ready.
- Publishing a GitHub release (tag like `v1.4.0`) triggers
  `.github/workflows/docker-publish.yml`, which runs the tests and pushes the
  image (amd64 + arm64). Never merge PRs, push to `main`, or publish releases
  yourself unless explicitly asked.

## Layout

- `app.py` — creates the app, registers blueprints, context processor,
  APScheduler background jobs.
- `db/` — all database code. `connection.py` (paths, allowlists),
  `init_db.py` (schema + additive migrations via `_add_column_if_missing`),
  `applications.py`, `settings.py`, `statuses.py`, `reminders.py`, …
  Import as `import db`.
- `routes/` — one blueprint per area (applications, import_, export,
  settings_routes, auth, api, …).
- `templates/` — Jinja templates extending `base.html`.
- `static/js/` — page scripts. The template sets a small
  `window.<PAGE>_CONFIG` object (URLs via `url_for(...) | tojson`, flags) and
  loads the script with `?v={{ app_version }}` so the PWA service worker never
  serves a stale copy. Don't put large inline `<script>` blocks in templates.
- `update_check.py` — daily GitHub release check and navbar "Update" badge.
- `tests/` — pytest suite. `conftest.py` points `DB_PATH` at a temp file, sets
  `DEPLOYMENT_MODE=local` and `JOB_TRACKER_DISABLE_SCHEDULER=1`, and wipes
  applications/companies before each test.
- `docs/` — user-guide, admin-guide, architecture, updating. `CHANGELOG.md`.

## Commands

```bash
pip install -r requirements.txt pytest
python -m pytest            # run the tests
python app.py               # run locally on http://localhost:5000
```

## Conventions and gotchas

- `run_script.py` uses CRLF line endings — keep them if you edit it.
- Schema changes must be additive and run automatically on startup (users
  upgrade by pulling a new image). New columns go in the allowlists in
  `db/connection.py` and the migration list in `db/init_db.py`.
- Multi-user mode: queries for user data filter by `user_id` wherever the
  existing code does. Single-user/local mode passes `user_id=None`.
- CSV import fields are defined in `db/applications.py` (`IMPORTABLE_FIELDS`)
  and `routes/import_.py` (`CSV_IMPORT_FIELDS`); keep them in step with the
  CSV export columns in `routes/export.py` so export → edit → re-import works.
- Release tags may look like `v1.3.0`, `V1.2.4` or `V1.2.4A`;
  `update_check.parse_version` handles all of these.
- Keep behaviour unchanged unless the task says otherwise. Australian English
  in user-facing text.

## Definition of done

- Tests added/updated for every change; the whole suite passes.
- App started locally and the main pages (dashboard, year view, add/edit form,
  settings sections, import, export) loaded in a browser with no JavaScript
  errors.
- `CHANGELOG.md` and the relevant docs updated.
- PR description says what changed, how it was tested, and anything that must
  be done on the NAS after updating (new env vars, volume changes, …).

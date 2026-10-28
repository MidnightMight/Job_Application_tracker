"""Flask application entry point.

Creates the app, registers all blueprints, sets up the context processor
and the background scheduler.  All route logic lives in routes/.
All database logic lives in db/.
"""

import logging
import os
import platform as _platform_module
import secrets
from urllib.parse import urlparse

from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import HTTPException
from apscheduler.schedulers.background import BackgroundScheduler

import db
import update_check

# Release images set APP_VERSION from the release tag (see docker-publish.yml);
# the fallback is for running from source and should match the latest release.
APP_VERSION = os.environ.get("APP_VERSION", "").strip().lstrip("vV") or "1.3.5"
GITHUB_REPO = "MidnightMight/Job_Application_tracker"


def _detect_deployment_mode() -> str:
    """Return 'docker' (full features) or 'local' (single-user, no AI).

    Precedence:
    1. DEPLOYMENT_MODE env var (explicit override)
    2. Presence of /.dockerenv (running inside a container)
    3. DB_PATH env var set (Docker Compose / container typically sets this)
    4. OS: Windows or macOS → 'local'; Linux/other → 'docker'
    """
    explicit = os.environ.get("DEPLOYMENT_MODE", "").lower()
    if explicit in ("docker", "local"):
        return explicit
    if os.path.exists("/.dockerenv"):
        return "docker"
    if os.environ.get("DB_PATH"):
        return "docker"
    system = _platform_module.system()
    if system in ("Windows", "Darwin"):
        return "local"
    return "docker"


def _load_secret_key() -> str:
    """Return the session signing key.

    SECRET_KEY from the environment wins.  Otherwise a random key is generated
    once and kept in a `secret_key` file next to the database (/data in
    Docker), so sessions survive restarts and image updates.
    """
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key
    key_path = os.path.join(os.path.dirname(db.DB_PATH) or ".", "secret_key")
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        with open(key_path, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
        # An empty file (e.g. a crash mid-write) is replaced below.
        fd = os.open(key_path, os.O_WRONLY | os.O_TRUNC)
    key = secrets.token_hex(32)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key)
    return key


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = _load_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
# Tokens last as long as the session, so a form left open for hours still saves.
app.config["WTF_CSRF_TIME_LIMIT"] = None
csrf = CSRFProtect(app)

DEPLOYMENT_MODE: str = _detect_deployment_mode()
app.config["DEPLOYMENT_MODE"] = DEPLOYMENT_MODE
app.config["APP_VERSION"]     = APP_VERSION
app.config["GITHUB_REPO"]     = GITHUB_REPO

# ---------------------------------------------------------------------------
# Logging — write DEBUG+ to a log file next to the database; INFO+ to console
# ---------------------------------------------------------------------------

def _configure_logging():
    log_dir = os.path.dirname(db.DB_PATH) or "."
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — full DEBUG detail, rotates at 2 MB, keeps 3 backups
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler — INFO and above only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("tzlocal").setLevel(logging.WARNING)

    return log_path


_log_path = _configure_logging()
logger = logging.getLogger(__name__)
logger.info("Job Application Tracker starting (version %s, mode=%s)", APP_VERSION, DEPLOYMENT_MODE)
logger.info("Database path : %s", db.DB_PATH)
logger.info("Log file path : %s", _log_path)

import json as _json

db.init_db()

app.jinja_env.globals["enumerate"] = enumerate
app.jinja_env.globals["how_applied_options"] = db.HOW_APPLIED_OPTIONS


def _status_label(status) -> str:
    """Status as words for display; the "Select_Status" placeholder reads "No status"."""
    return "No status" if status in (None, "", "Select_Status") else str(status).replace("_", " ")


app.jinja_env.filters["status_label"] = _status_label


def _month_short(value) -> str:
    """"2026-11-03" -> "Nov" (blank when it isn't a date)."""
    from datetime import date as _date
    try:
        return _date.fromisoformat(str(value)[:10]).strftime("%b")
    except ValueError:
        return ""


app.jinja_env.filters["month_short"] = _month_short
app.jinja_env.globals["priority_levels"] = db.PRIORITY_LEVELS
app.jinja_env.filters["from_json"] = lambda s: _json.loads(s) if s else []

# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------

from routes.auth            import bp as auth_bp
from routes.onboarding      import bp as onboarding_bp
from routes.dashboard       import bp as dashboard_bp
from routes.applications    import bp as applications_bp
from routes.import_         import bp as import_bp
from routes.companies       import bp as companies_bp
from routes.inbox           import bp as inbox_bp
from routes.settings_routes import bp as settings_bp
from routes.api             import bp as api_bp
from routes.export          import bp as export_bp
from routes.admin_db        import bp as admin_db_bp
from routes.report          import bp as report_bp
from routes.insights        import bp as insights_bp
from routes.calendar_feed   import bp as calendar_feed_bp

app.register_blueprint(auth_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(applications_bp)
app.register_blueprint(import_bp)
app.register_blueprint(companies_bp)
app.register_blueprint(inbox_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(api_bp)
app.register_blueprint(export_bp)
app.register_blueprint(admin_db_bp)
app.register_blueprint(report_bp)
app.register_blueprint(insights_bp)
app.register_blueprint(calendar_feed_bp)

# ---------------------------------------------------------------------------
# Onboarding gate
# ---------------------------------------------------------------------------

_ONBOARDING_EXEMPT = {"onboarding.onboarding", "auth.login", "auth.logout", "auth.setup_password", "static",
                      "healthz", "calendar_feed.feed"}


@app.before_request
def _check_onboarding():
    """Redirect every request to /onboarding until the first-run wizard is done."""
    if request.endpoint in _ONBOARDING_EXEMPT or request.endpoint is None:
        return
    if db.get_setting("onboarding_complete", "0") == "0":
        return redirect(url_for("onboarding.onboarding"))


# ---------------------------------------------------------------------------
# Health check (Docker HEALTHCHECK, uptime monitors) — no login needed
# ---------------------------------------------------------------------------

@app.route("/healthz")
def healthz():
    try:
        conn = db.get_connection()
        try:
            conn.execute("SELECT 1 FROM settings LIMIT 1").fetchall()
        finally:
            conn.close()
    except Exception:
        logger.exception("Health check failed")
        return jsonify(status="error"), 503
    return jsonify(status="ok")


@app.after_request
def _allow_root_service_worker(response):
    """The service worker lives in /static but controls the whole site."""
    if request.path == "/static/sw.js":
        response.headers["Service-Worker-Allowed"] = "/"
    return response


# ---------------------------------------------------------------------------
# CSRF failures — usually an old tab or an expired session
# ---------------------------------------------------------------------------

@app.errorhandler(CSRFError)
def _handle_csrf_error(exc):
    logger.warning("CSRF check failed on %s %s: %s", request.method, request.path, exc.description)
    message = "The form had expired. Please try again."
    is_form = request.mimetype in ("application/x-www-form-urlencoded", "multipart/form-data")
    if not is_form or request.path.startswith("/api/"):
        return jsonify(ok=False, error=message), 400
    flash(message, "warning")
    from routes.auth import _safe_path
    back = _safe_path(urlparse(request.referrer or "").path) if request.referrer else None
    return redirect(back or url_for("dashboard.dashboard"))


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    from datetime import date as _date
    from flask import session
    from routes.auth import current_user_id, is_current_user_admin
    user_id = current_user_id()

    # Per-user AI settings (empty defaults when not logged in)
    user_ai_cfg = db.get_user_ai_settings(user_id)

    # Profile completeness: check user's own profile first, fall back to global settings
    if user_id is not None:
        _profile_complete = bool(
            user_ai_cfg.get("profile_skills",     "").strip()
            or user_ai_cfg.get("profile_experience", "").strip()
            or user_ai_cfg.get("profile_summary",    "").strip()
        )
    else:
        _profile_complete = bool(
            db.get_setting("user_profile_skills",     "").strip()
            or db.get_setting("user_profile_experience", "").strip()
            or db.get_setting("user_profile_summary",    "").strip()
        )

    ollama_on = db.get_setting("ollama_enabled", "0") == "1"
    # AI is available when the admin enabled Ollama OR the user has their own API key.
    ai_available = ollama_on or db.user_has_own_ai(user_id)

    return {
        "years":                  db.get_dynamic_years(user_id=user_id),
        "current_year_for_footer": _date.today().year,
        "unread_reminder_count":  db.get_unread_reminder_count(user_id=user_id),
        "login_enabled":          db.get_setting("login_enabled", "0") == "1",
        "current_user":           session.get("username"),
        "current_is_admin":       is_current_user_admin(),
        "app_version":            APP_VERSION,
        "ollama_enabled":         ollama_on,
        "ai_available":           ai_available,
        "ai_fit_enabled":         db.get_setting("ai_fit_enabled", "0") == "1",
        "user_profile_complete":  _profile_complete,
        "deployment_mode":        DEPLOYMENT_MODE,
        "status_styles":          db.get_status_styles(user_id=user_id),
        **update_check.cached_update_info(APP_VERSION),
    }


# ---------------------------------------------------------------------------
# Background scheduler — reminder checks
# ---------------------------------------------------------------------------

def _check_and_create_reminders():
    """Scheduled task: create inbox reminders for long-pending applications."""
    try:
        if db.get_setting("reminder_enabled", "1") != "1":
            return
        days = int(db.get_setting("reminder_days", "3"))
        for app_record in db.get_pending_for_reminders(days):
            msg = (
                f"'{app_record['job_desc'] or 'Application'}' at {app_record['company']} "
                f"has been pending ({app_record['status'].replace('_', ' ')}) "
                f"for {app_record['duration']} days."
            )
            db.create_reminder(app_record["id"], msg)
        _create_next_step_reminders()
    except Exception:
        logger.exception("Reminder check failed")


def _create_next_step_reminders():
    """Inbox reminder when an application's next step is due (once per due date)."""
    from datetime import date as _date
    today = _date.today().isoformat()
    for app_record in db.get_due_next_steps_without_reminder():
        what = (app_record.get("next_action") or "").strip() or "Next step"
        when = "today" if app_record["next_action_date"][:10] == today else (
            f"overdue since {app_record['next_action_date'][:10]}")
        msg = (f"{what} for '{app_record['job_desc'] or 'Application'}' at "
               f"{app_record['company']} is due {when}.")
        db.create_reminder(app_record["id"], msg, reminder_type="next_step")


def _auto_archive_finished_applications():
    """Scheduled task: archive Rejected / Not Applying / Job Expired applications
    after the number of days set in Settings (0 = off)."""
    try:
        days = int(db.get_setting("auto_archive_days", "0") or 0)
        if days > 0:
            count = db.auto_archive_finished(days)
            if count:
                logger.info("Auto-archived %s finished application(s)", count)
    except Exception:
        logger.exception("Auto-archive failed")


def _check_stale_submitted_applications():
    """Scheduled task: stale-application logic for the submitted → rejected range.

    * Stall check-in (threshold 1): no status change AND no recorded contact →
      create a 'Check in with HR' inbox reminder.
    * Likely Rejected (threshold 2): no status change →
      lower success_chance to ≤ 10 % and create an 'Update to Likely Rejected?' reminder.
    """
    from datetime import date as _date
    try:
        stall_value = int(db.get_setting("stale_threshold_value", "2"))
        stall_unit  = db.get_setting("stale_threshold_unit", "weeks")
        stall_days  = stall_value * (7 if stall_unit == "weeks" else 1)

        rejected_value = int(db.get_setting("rejected_threshold_value", "4"))
        rejected_unit  = db.get_setting("rejected_threshold_unit", "weeks")
        rejected_days  = rejected_value * (7 if rejected_unit == "weeks" else 1)

        today = _date.today()

        for app_record in db.get_stalled_submitted_applications(stall_days):
            # Compute stale duration: days since most recent activity (status or contact).
            last_contact = app_record.get("last_contact_date") or ""
            last_status  = (app_record.get("status_changed_at") or
                            app_record.get("date_applied") or "")
            last_activity = max(last_contact[:10], last_status[:10]) if last_contact else last_status[:10]
            try:
                from datetime import datetime as _dt
                stale_days = (_date.today() - _dt.fromisoformat(last_activity).date()).days
            except Exception:
                stale_days = app_record["duration"]
            msg = (
                f"No activity for {stale_days} day(s) on "
                f"'{app_record['job_desc'] or 'Application'}' at {app_record['company']} "
                f"({app_record['status'].replace('_', ' ')}). "
                "Consider checking in with HR."
            )
            db.create_reminder(app_record["id"], msg, reminder_type="stall_checkin")

        for app_record in db.get_likely_rejected_applications(rejected_days):
            db.lower_success_chance_for_stale(app_record["id"])
            # Compute stale duration: days since last status change.
            last_status = (app_record.get("status_changed_at") or
                           app_record.get("date_applied") or "")
            try:
                from datetime import datetime as _dt
                days_since_status_change = (_date.today() - _dt.fromisoformat(last_status[:10]).date()).days
            except Exception:
                days_since_status_change = app_record["duration"]
            msg = (
                f"'{app_record['job_desc'] or 'Application'}' at {app_record['company']} "
                f"has had no status change for {days_since_status_change} day(s). "
                "Consider updating the status to Likely Rejected."
            )
            db.create_reminder(app_record["id"], msg, reminder_type="likely_rejected")
    except Exception:
        logger.exception("Stale-application check failed")


def _check_for_update():
    """Scheduled task: look for a newer GitHub release once a day (cached)."""
    update_check.refresh_latest_release(GITHUB_REPO)


# ---------------------------------------------------------------------------
# Scheduler interval helpers
# ---------------------------------------------------------------------------

# Map setting value → APScheduler interval kwargs.
_INTERVAL_MAP = {
    "1h":  {"hours":   1},
    "6h":  {"hours":   6},
    "12h": {"hours":  12},
    "1d":  {"hours":  24},
    "2d":  {"hours":  48},
    "3d":  {"hours":  72},
    "7d":  {"hours": 168},
}


def _interval_kwargs() -> dict:
    """Return APScheduler interval kwargs for the currently configured check_interval."""
    val = db.get_setting("check_interval", "1h")
    return _INTERVAL_MAP.get(val, {"hours": 1})


def _scheduler_enabled() -> bool:
    """The scheduler runs unless disabled (tests) or in the reloader's watcher process."""
    if os.environ.get("JOB_TRACKER_DISABLE_SCHEDULER") == "1":
        return False
    return os.environ.get("WERKZEUG_RUN_MAIN") != "false"


def _reschedule_jobs(interval_key: str):
    """Reschedule both background jobs to the given interval (live, no restart needed)."""
    if _scheduler_enabled():
        kwargs = _INTERVAL_MAP.get(interval_key, {"hours": 1})
        for job_id in ("reminders", "stale_check"):
            _scheduler.reschedule_job(job_id, trigger="interval", **kwargs)
        logger.info("Scheduler jobs rescheduled to interval: %s (%s)", interval_key, kwargs)


if _scheduler_enabled():
    _scheduler = BackgroundScheduler(daemon=True)
    _init_kwargs = _interval_kwargs()
    _scheduler.add_job(_check_and_create_reminders, "interval", id="reminders", **_init_kwargs)
    _scheduler.add_job(_check_stale_submitted_applications, "interval", id="stale_check", **_init_kwargs)
    _scheduler.add_job(_auto_archive_finished_applications, "interval", id="auto_archive", hours=24)
    # Daily update check; first run straight away in the background.
    from datetime import datetime as _datetime
    _scheduler.add_job(_check_for_update, "interval", id="update_check", hours=24,
                       next_run_time=_datetime.now())
    _scheduler.start()
    _check_and_create_reminders()
    _check_stale_submitted_applications()
    _auto_archive_finished_applications()


# ---------------------------------------------------------------------------
# Unhandled-exception logger — captures the full traceback for every 500
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def _handle_unhandled_exception(exc):
    if isinstance(exc, HTTPException):
        return exc  # 404, 405 and friends are normal responses, not crashes
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.path
    )
    raise exc


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

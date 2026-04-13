"""Flask application entry point.

Creates the app, registers all blueprints, sets up the context processor
and the background scheduler.  All route logic lives in routes/.
All database logic lives in db/.
"""

import logging
import os
import platform as _platform_module

from flask import Flask, redirect, request, url_for
from apscheduler.schedulers.background import BackgroundScheduler

import db

APP_VERSION = "1.2.2"
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


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "job-tracker-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

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

# ---------------------------------------------------------------------------
# Onboarding gate
# ---------------------------------------------------------------------------

_ONBOARDING_EXEMPT = {"onboarding.onboarding", "auth.login", "auth.logout", "auth.setup_password", "static"}


@app.before_request
def _check_onboarding():
    """Redirect every request to /onboarding until the first-run wizard is done."""
    if request.endpoint in _ONBOARDING_EXEMPT or request.endpoint is None:
        return
    if db.get_setting("onboarding_complete", "0") == "0":
        return redirect(url_for("onboarding.onboarding"))


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
    except Exception:
        pass


if os.environ.get("WERKZEUG_RUN_MAIN") != "false":
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_check_and_create_reminders, "interval", hours=1, id="reminders")
    _scheduler.start()
    _check_and_create_reminders()


# ---------------------------------------------------------------------------
# Unhandled-exception logger — captures the full traceback for every 500
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def _handle_unhandled_exception(exc):
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.path
    )
    raise exc


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

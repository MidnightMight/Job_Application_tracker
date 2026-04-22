"""Settings routes (general, statuses, users, AI, updates)."""

import json
import urllib.error
import urllib.request

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, jsonify, current_app,
)
from werkzeug.security import generate_password_hash

import db
from .auth import login_required, admin_required, current_user_id, is_current_user_admin

bp = Blueprint("settings_routes", __name__)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    DEPLOYMENT_MODE = current_app.config.get("DEPLOYMENT_MODE", "docker")
    APP_VERSION = current_app.config.get("APP_VERSION", "")
    section = request.args.get("section", "general")
    user_id = current_user_id()
    is_admin = is_current_user_admin()

    # Redirect non-admins away from admin-only sections
    if section in ("users",) and not is_admin:
        flash("Administrator access is required for that section.", "danger")
        return redirect(url_for("settings_routes.settings", section="general"))

    if request.method == "POST":
        action = request.form.get("action", "save_general")

        if action == "save_general":
            db.set_setting("reminder_enabled", "1" if request.form.get("reminder_enabled") else "0")
            days = request.form.get("reminder_days", "3").strip()
            if days.isdigit() and int(days) >= 1:
                db.set_setting("reminder_days", days)
            else:
                flash("Reminder days must be a positive integer.", "danger")
                return redirect(url_for("settings_routes.settings", section="general"))
            db.set_setting(
                "company_pool_enabled",
                "1" if request.form.get("company_pool_enabled") else "0",
            )

            # Stale application thresholds
            stale_val = request.form.get("stale_threshold_value", "2").strip()
            stale_unit = request.form.get("stale_threshold_unit", "weeks").strip()
            if stale_val.isdigit() and int(stale_val) >= 1:
                db.set_setting("stale_threshold_value", stale_val)
            else:
                flash("Stale Application threshold must be a positive integer.", "danger")
                return redirect(url_for("settings_routes.settings", section="general"))
            if stale_unit in ("days", "weeks"):
                db.set_setting("stale_threshold_unit", stale_unit)

            rejected_val = request.form.get("rejected_threshold_value", "4").strip()
            rejected_unit = request.form.get("rejected_threshold_unit", "weeks").strip()
            if rejected_val.isdigit() and int(rejected_val) >= 1:
                db.set_setting("rejected_threshold_value", rejected_val)
            else:
                flash("Likely Rejected threshold must be a positive integer.", "danger")
                return redirect(url_for("settings_routes.settings", section="general"))
            if rejected_unit in ("days", "weeks"):
                db.set_setting("rejected_threshold_unit", rejected_unit)

            # Check schedule interval
            _valid_intervals = {"1h", "6h", "12h", "1d", "2d", "3d", "7d"}
            check_interval = request.form.get("check_interval", "1h").strip()
            if check_interval not in _valid_intervals:
                check_interval = "1h"
            db.set_setting("check_interval", check_interval)

            default_sort = request.form.get("applications_default_sort", "status").strip().lower()
            if default_sort not in {"date", "status"}:
                default_sort = "status"
            db.set_setting("applications_default_sort", default_sort)
            # Apply the new interval to the running scheduler immediately.
            from app import _reschedule_jobs
            _reschedule_jobs(check_interval)

            flash("General settings saved.", "success")
            return redirect(url_for("settings_routes.settings", section="general"))

        elif action == "save_security":
            if not is_admin:
                flash("Administrator access is required.", "danger")
                return redirect(url_for("settings_routes.settings", section="general"))
            if DEPLOYMENT_MODE == "local":
                flash("Login / multi-user settings are not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="users"))
            login_enabled = "1" if request.form.get("login_enabled") else "0"
            if login_enabled == "1" and db.count_users() == 0:
                flash("Cannot enable login — no users exist. Add a user first.", "danger")
                return redirect(url_for("settings_routes.settings", section="users"))
            db.set_setting("login_enabled", login_enabled)
            if login_enabled == "1":
                users = db.get_users()
                admins = [u for u in users if u["is_admin"]]
                first_user = (admins or users)[0]
                db.reassign_null_user_data(first_user["id"])
            flash("Security settings saved.", "success")
            return redirect(url_for("settings_routes.settings", section="users"))

        elif action == "add_status":
            ok, msg = db.add_status(
                request.form.get("name", ""),
                bg_color=request.form.get("bg_color", ""),
                text_color=request.form.get("text_color", ""),
                user_id=user_id,
            )
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="statuses"))

        elif action == "delete_status":
            ok, msg = db.delete_status(request.form.get("name", ""), user_id=user_id)
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="statuses"))

        elif action in ("move_status_up", "move_status_down"):
            direction = "up" if action == "move_status_up" else "down"
            ok, msg = db.move_status(request.form.get("name", ""), direction, user_id=user_id)
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="statuses"))

        elif action == "update_status_colors":
            ok, msg = db.update_status_colors(
                request.form.get("name", ""),
                bg_color=request.form.get("bg_color", ""),
                text_color=request.form.get("text_color", ""),
                user_id=user_id,
            )
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="statuses"))

        elif action == "add_user":
            if not is_admin:
                flash("Administrator access is required.", "danger")
                return redirect(url_for("settings_routes.settings", section="general"))
            if DEPLOYMENT_MODE == "local":
                flash("User management is not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="users"))
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password2 = request.form.get("password2", "")
            new_is_admin = bool(request.form.get("is_admin"))
            if not username:
                flash("Username is required.", "danger")
            elif password and password != password2:
                flash("Passwords do not match.", "danger")
            elif password and len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
            else:
                if password:
                    pw_hash = generate_password_hash(password)
                    needs_setup = False
                else:
                    # No password supplied — user must set it on first login.
                    pw_hash = ""
                    needs_setup = True
                ok, msg = db.add_user(username, pw_hash, new_is_admin,
                                      needs_password_setup=needs_setup)
                if ok and needs_setup:
                    msg += " They will be prompted to set a password on first login."
                flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="users"))

        elif action == "delete_user":
            if not is_admin:
                flash("Administrator access is required.", "danger")
                return redirect(url_for("settings_routes.settings", section="general"))
            if DEPLOYMENT_MODE == "local":
                flash("User management is not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="users"))
            target_user_id = request.form.get("user_id", "")
            if target_user_id.isdigit():
                ok, msg = db.delete_user(int(target_user_id))
                flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="users"))

        elif action == "save_ai":
            if not is_admin:
                flash("Administrator access is required to change AI settings.", "danger")
                return redirect(url_for("settings_routes.settings", section="ai"))
            if DEPLOYMENT_MODE == "local":
                flash("AI settings are not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="ai"))
            db.set_setting("ollama_enabled", "1" if request.form.get("ollama_enabled") else "0")
            db.set_setting("ai_fit_enabled", "1" if request.form.get("ai_fit_enabled") else "0")
            ollama_url = request.form.get("ollama_url", "").strip()
            if ollama_url:
                db.set_setting("ollama_url", ollama_url)
            db.set_setting(
                "ollama_model",
                request.form.get("ollama_model", "llama3").strip() or "llama3",
            )
            flash("AI settings saved.", "success")
            return redirect(url_for("settings_routes.settings", section="ai"))

        elif action == "save_profile":
            if DEPLOYMENT_MODE == "local":
                flash("AI profile settings are not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="ai"))
            profile_user_id = current_user_id()
            skills     = request.form.get("user_profile_skills",     "").strip()
            experience = request.form.get("user_profile_experience", "").strip()
            summary    = request.form.get("user_profile_summary",    "").strip()
            if profile_user_id is not None:
                db.save_user_ai_settings(profile_user_id, {
                    "profile_skills":     skills,
                    "profile_experience": experience,
                    "profile_summary":    summary,
                })
            else:
                # Single-user mode: keep using global settings.
                db.set_setting("user_profile_skills",     skills)
                db.set_setting("user_profile_experience", experience)
                db.set_setting("user_profile_summary",    summary)
            flash("Your profile has been saved.", "success")
            return redirect(url_for("settings_routes.settings", section="ai"))

        elif action == "save_user_ai":
            if DEPLOYMENT_MODE == "local":
                flash("AI settings are not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="ai"))
            profile_user_id = current_user_id()
            if profile_user_id is None:
                flash("You must be logged in to save personal AI settings.", "warning")
                return redirect(url_for("settings_routes.settings", section="ai"))
            # Toggle: 1 = use admin's server, 0 = use own settings.
            use_admin_ai = 1 if request.form.get("use_admin_ai") == "1" else 0
            provider = request.form.get("ai_provider", "ollama").strip()
            if provider not in ("ollama", "openai", "anthropic", "custom"):
                provider = "ollama"
            api_key  = request.form.get("api_key",  "").strip()
            api_url  = request.form.get("api_url",  "").strip()
            ai_model = request.form.get("ai_model", "").strip()
            fields = {
                "use_admin_ai": use_admin_ai,
                "ai_provider":  provider,
                "api_url":      api_url,
                "ai_model":     ai_model,
            }
            # Only overwrite the stored API key when a non-empty value was submitted.
            if api_key:
                fields["api_key"] = api_key
            db.save_user_ai_settings(profile_user_id, fields)
            flash("Your AI provider settings have been saved.", "success")
            return redirect(url_for("settings_routes.settings", section="ai"))

        flash("Unknown action.", "warning")
        return redirect(url_for("settings_routes.settings", section=section))

    current = db.get_all_settings()
    statuses = db.get_status_options(user_id=user_id)
    status_rows = db.get_status_rows(user_id=user_id)
    status_styles = db.get_status_styles(user_id=user_id)
    users = db.get_users()
    for u in users:
        last_login = (u.get("last_login_at") or "").replace("T", " ")
        u["last_login_display"] = last_login[:16] if last_login else "—"
    user_ai_cfg = db.get_user_ai_settings(user_id)
    admin_ai_on = current.get("ollama_enabled", "0") == "1"
    user_ai_on = db.user_has_own_ai(user_id)
    return render_template(
        "settings.html",
        settings=current,
        section=section,
        statuses=statuses,
        status_rows=status_rows,
        status_styles=status_styles,
        users=users,
        app_version=APP_VERSION,
        protected_statuses=db.PROTECTED_STATUSES,
        current_is_admin=is_admin,
        user_ai_settings=user_ai_cfg,
        profile_ai_enabled=(admin_ai_on or user_ai_on),
    )


@bp.route("/settings/reorder-statuses", methods=["POST"])
@login_required
def reorder_statuses():
    """AJAX endpoint: receive JSON list of status names and save new sort order."""
    data = request.get_json(silent=True) or {}
    names = data.get("names")
    if not isinstance(names, list):
        return jsonify({"ok": False, "error": "Invalid payload."}), 400
    user_id = current_user_id()
    ok, msg = db.reorder_statuses(names, user_id=user_id)
    return jsonify({"ok": ok, "message": msg})


@bp.route("/settings/ollama-test", methods=["POST"])
@login_required
def ollama_test():
    ollama_url = request.json.get("url", db.get_setting("ollama_url", "http://localhost:11434"))
    ollama_url = ollama_url.rstrip("/")
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        models = [m.get("name", "") for m in data.get("models", [])]
        return jsonify({"ok": True, "models": models})
    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not connect to Ollama server. Check the URL and ensure the server is running."})
    except Exception:
        return jsonify({"ok": False, "error": "Could not connect to Ollama server."})


@bp.route("/settings/check-update")
@login_required
def check_update():
    APP_VERSION = current_app.config.get("APP_VERSION", "")
    GITHUB_REPO = current_app.config.get("GITHUB_REPO", "")
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Job-Tracker-App",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        latest_tag = data.get("tag_name", "").lstrip("v")
        html_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
        is_newer = _version_is_newer(latest_tag, APP_VERSION)
        return jsonify({
            "ok": True,
            "current": APP_VERSION,
            "latest": latest_tag,
            "update_available": is_newer,
            "html_url": html_url,
        })
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            error = "No releases have been published on GitHub yet."
        elif exc.code in (403, 429):
            error = "GitHub API rate limit reached. Please try again in a few minutes."
        else:
            error = f"GitHub returned an unexpected error (HTTP {exc.code})."
        return jsonify({"ok": False, "error": error, "current": APP_VERSION})
    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not reach GitHub. Check your internet connection.", "current": APP_VERSION})
    except Exception:
        return jsonify({"ok": False, "error": "An unexpected error occurred while checking for updates.", "current": APP_VERSION})


def _version_is_newer(latest: str, current: str) -> bool:
    try:
        l_parts = [int(x) for x in latest.split(".")]
        c_parts = [int(x) for x in current.split(".")]
        while len(l_parts) < len(c_parts):
            l_parts.append(0)
        while len(c_parts) < len(l_parts):
            c_parts.append(0)
        return l_parts > c_parts
    except Exception:
        return False


# Backward-compat redirect for the old /statuses route.
@bp.route("/statuses", methods=["GET", "POST"])
@login_required
def manage_statuses():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            ok, msg = db.add_status(request.form.get("name", ""))
            flash(msg, "success" if ok else "danger")
        elif action == "delete":
            ok, msg = db.delete_status(request.form.get("name", ""))
            flash(msg, "success" if ok else "danger")
    return redirect(url_for("settings_routes.settings", section="statuses"))

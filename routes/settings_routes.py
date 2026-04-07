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
from .auth import login_required

bp = Blueprint("settings_routes", __name__)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    DEPLOYMENT_MODE = current_app.config.get("DEPLOYMENT_MODE", "docker")
    APP_VERSION = current_app.config.get("APP_VERSION", "")
    section = request.args.get("section", "general")

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
            flash("General settings saved.", "success")
            return redirect(url_for("settings_routes.settings", section="general"))

        elif action == "save_security":
            if DEPLOYMENT_MODE == "local":
                flash("Login / multi-user settings are not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="users"))
            login_enabled = "1" if request.form.get("login_enabled") else "0"
            if login_enabled == "1" and db.count_users() == 0:
                flash("Cannot enable login — no users exist. Add a user first.", "danger")
                return redirect(url_for("settings_routes.settings", section="users"))
            db.set_setting("login_enabled", login_enabled)
            flash("Security settings saved.", "success")
            return redirect(url_for("settings_routes.settings", section="users"))

        elif action == "add_status":
            ok, msg = db.add_status(request.form.get("name", ""))
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="statuses"))

        elif action == "delete_status":
            ok, msg = db.delete_status(request.form.get("name", ""))
            flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="statuses"))

        elif action == "add_user":
            if DEPLOYMENT_MODE == "local":
                flash("User management is not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="users"))
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password2 = request.form.get("password2", "")
            is_admin = bool(request.form.get("is_admin"))
            if not username or not password:
                flash("Username and password are required.", "danger")
            elif password != password2:
                flash("Passwords do not match.", "danger")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
            else:
                pw_hash = generate_password_hash(password)
                ok, msg = db.add_user(username, pw_hash, is_admin)
                flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="users"))

        elif action == "delete_user":
            if DEPLOYMENT_MODE == "local":
                flash("User management is not available in local mode.", "warning")
                return redirect(url_for("settings_routes.settings", section="users"))
            user_id = request.form.get("user_id", "")
            if user_id.isdigit():
                ok, msg = db.delete_user(int(user_id))
                flash(msg, "success" if ok else "danger")
            return redirect(url_for("settings_routes.settings", section="users"))

        elif action == "save_ai":
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
            db.set_setting("user_profile_skills",     request.form.get("user_profile_skills",     "").strip())
            db.set_setting("user_profile_experience", request.form.get("user_profile_experience", "").strip())
            db.set_setting("user_profile_summary",    request.form.get("user_profile_summary",    "").strip())
            flash("Your profile has been saved.", "success")
            return redirect(url_for("settings_routes.settings", section="ai"))

        flash("Unknown action.", "warning")
        return redirect(url_for("settings_routes.settings", section=section))

    current = db.get_all_settings()
    statuses = db.get_status_options()
    users = db.get_users()
    return render_template(
        "settings.html",
        settings=current,
        section=section,
        statuses=statuses,
        users=users,
        app_version=APP_VERSION,
        protected_statuses=db.PROTECTED_STATUSES,
    )


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
    except Exception:
        return jsonify({"ok": False, "error": "Could not reach GitHub to check for updates.", "current": APP_VERSION})


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

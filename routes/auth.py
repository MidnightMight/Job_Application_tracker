"""Authentication: login_required decorator and login/logout routes."""

import functools

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db

bp = Blueprint("auth", __name__)

# Only paths starting with / and containing safe URL characters are allowed.
_PATH_OK_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "0123456789/_-.?=&%+#"
)


def _safe_path(path: str) -> str | None:
    """Return path if it is a safe relative URL path, otherwise None.

    The path must:
    - Start with exactly one forward slash (not //)
    - Contain only explicitly-allowed characters
    - Not include a scheme or netloc
    """
    if not path or not path.startswith("/") or path.startswith("//"):
        return None
    if len(path) > 2048:
        return None
    if not all(c in _PATH_OK_CHARS for c in path):
        return None
    return path


def current_user_id():
    """Return the logged-in user's ID when login is enabled, else None.

    Returns None in single-user (login-disabled) mode so that DB queries
    show all records without any user filter.
    """
    if db.get_setting("login_enabled", "0") == "1":
        return session.get("user_id")
    return None


def is_current_user_admin() -> bool:
    """Return True when the current session belongs to an admin user.

    Always returns True when login is disabled (single-user mode).
    """
    if db.get_setting("login_enabled", "0") != "1":
        return True
    return bool(session.get("is_admin"))


def login_required(f):
    """Decorator: redirect to login if auth is enabled and user is not logged in."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if db.get_setting("login_enabled", "0") == "1":
            if not session.get("user_id"):
                # Store only the server-side path (never user-provided input).
                session["login_next"] = request.path
                return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: require admin role (implies login_required).

    In single-user mode (login disabled) every request is treated as admin.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if db.get_setting("login_enabled", "0") == "1":
            if not session.get("user_id"):
                session["login_next"] = request.path
                return redirect(url_for("auth.login"))
            if not session.get("is_admin"):
                flash("Administrator access is required for this page.", "danger")
                return redirect(url_for("dashboard.dashboard"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/login", methods=["GET", "POST"])
def login():
    if db.get_setting("login_enabled", "0") != "1":
        return redirect(url_for("dashboard.dashboard"))
    if session.get("user_id"):
        return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user_by_username(username)

        # First-time login: user exists, needs password setup, password left blank.
        if user and not password and user.get("needs_password_setup"):
            session["setup_user_id"] = user["id"]
            session["setup_username"] = user["username"]
            return redirect(url_for("auth.setup_password"))

        if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            db.update_user_last_login(user["id"])
            flash(f"Welcome back, {user['username']}!", "success")
            # Retrieve the server-stored path; never use form/query input for redirect.
            stored_path = session.pop("login_next", None)
            safe = _safe_path(stored_path) if stored_path else None
            return redirect(safe or url_for("dashboard.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/setup-password", methods=["GET", "POST"])
def setup_password():
    """First-time password setup for users who were created without a password."""
    user_id = session.get("setup_user_id")
    username = session.get("setup_username", "")
    if not user_id:
        # Nothing to set up — redirect to login.
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        errors = []
        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        elif password != password2:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("setup_password.html", username=username)

        db.set_user_password(user_id, generate_password_hash(password))
        session.pop("setup_user_id", None)
        session.pop("setup_username", None)

        # Log the user in now that their password is set.
        user = db.get_user_by_username(username)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            db.update_user_last_login(user["id"])
        flash("Password set successfully! Welcome.", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("setup_password.html", username=username)

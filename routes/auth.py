"""Authentication: login_required decorator and login/logout routes."""

import functools

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash

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
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
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

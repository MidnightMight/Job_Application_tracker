"""Authentication: login_required decorator and login/logout routes."""

import functools

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash

import db

bp = Blueprint("auth", __name__)


def login_required(f):
    """Decorator: redirect to login if auth is enabled and user is not logged in."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if db.get_setting("login_enabled", "0") == "1":
            if not session.get("user_id"):
                return redirect(url_for("auth.login", next=request.url))
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
            raw_next = request.form.get("next", "")
            from urllib.parse import urlparse as _urlparse
            _p = _urlparse(raw_next)
            _safe = (
                raw_next
                and raw_next.startswith("/")
                and not raw_next.startswith("//")
                and not _p.netloc
                and not _p.scheme
            )
            next_url = raw_next if _safe else url_for("dashboard.dashboard")
            return redirect(next_url)
        flash("Invalid username or password.", "danger")
    return render_template("login.html", next=request.args.get("next", ""))


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

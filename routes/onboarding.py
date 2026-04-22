"""Onboarding wizard routes."""

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for, current_app,
)
from werkzeug.security import generate_password_hash

import db
from .auth import login_required, current_user_id

bp = Blueprint("onboarding", __name__)


@bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    DEPLOYMENT_MODE = current_app.config.get("DEPLOYMENT_MODE", "docker")

    if db.get_setting("onboarding_complete", "0") == "1":
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "setup_admin":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password2 = request.form.get("password2", "")
            clear_demo = request.form.get("clear_demo") == "1"

            errors = []
            if not username:
                errors.append("Username is required.")
            if not password:
                errors.append("Password is required.")
            elif len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            elif password != password2:
                errors.append("Passwords do not match.")

            if errors:
                for e in errors:
                    flash(e, "danger")
                return render_template(
                    "onboarding.html",
                    step="admin",
                    deployment_mode=DEPLOYMENT_MODE,
                    narrator_name="O.t.t.o",
                )

            pw_hash = generate_password_hash(password)
            ok, msg = db.add_user(username, pw_hash, is_admin=True, onboarding_complete=True)
            if not ok:
                flash(msg, "danger")
                return render_template(
                    "onboarding.html",
                    step="admin",
                    deployment_mode=DEPLOYMENT_MODE,
                    narrator_name="O.t.t.o",
                )

            new_user = db.get_user_by_username(username)
            db.reassign_null_user_data(new_user["id"])
            db.set_setting("login_enabled", "1")
            session["user_id"] = new_user["id"]
            session["username"] = username

            if clear_demo:
                db.clear_demo_data()

            db.set_setting("onboarding_complete", "1")
            flash(f"Welcome, {username}! Your account has been created and login is enabled.", "success")
            return redirect(url_for("dashboard.dashboard"))

        elif action == "skip":
            clear_demo = request.form.get("clear_demo") == "1"
            if clear_demo:
                db.clear_demo_data()
            db.set_setting("onboarding_complete", "1")
            flash("Welcome to Job Tracker! You can set up login any time in Settings.", "info")
            return redirect(url_for("dashboard.dashboard"))

    if request.args.get("next_step") == "1":
        return render_template(
            "onboarding.html",
            step="admin",
            deployment_mode=DEPLOYMENT_MODE,
            narrator_name="O.t.t.o",
        )

    return render_template(
        "onboarding.html",
        step="welcome",
        deployment_mode=DEPLOYMENT_MODE,
        narrator_name="O.t.t.o",
    )


@bp.route("/onboarding/user", methods=["GET", "POST"])
@login_required
def user_onboarding():
    user_id = current_user_id()
    if user_id is None:
        return redirect(url_for("dashboard.dashboard"))

    user = db.get_user_by_id(user_id)
    if not user:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        db.set_user_onboarding_complete(user_id, True)
        flash("Welcome aboard — O.t.t.o is ready to help!", "success")
        return redirect(url_for("dashboard.dashboard"))

    if int(user.get("onboarding_complete", 0)) == 1:
        return redirect(url_for("dashboard.dashboard"))

    return render_template("user_onboarding.html", narrator_name="O.t.t.o")

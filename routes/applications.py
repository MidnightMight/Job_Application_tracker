"""Application CRUD and bulk-action routes."""

import logging
from datetime import date
from types import SimpleNamespace

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for,
)

import db
from .auth import login_required, current_user_id

bp = Blueprint("applications", __name__)
logger = logging.getLogger(__name__)


@bp.route("/application/<int:app_id>")
@login_required
def application_detail(app_id):
    user_id = current_user_id()
    application = db.get_application(app_id, user_id=user_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    timeline = db.get_application_timeline(app_id)
    return render_template(
        "application_detail.html",
        app=application,
        timeline=timeline,
    )


@bp.route("/application/add", methods=["GET", "POST"])
@login_required
def add_application():
    user_id = current_user_id()
    if request.method == "POST":
        company     = request.form.get("company", "").strip()
        job_desc    = request.form.get("job_desc", "").strip()
        date_applied = request.form.get("date_applied", "").strip()
        team        = request.form.get("team", "").strip()

        if request.form.get("force_add") != "1":
            duplicates = db.find_duplicate_applications(
                company, job_desc, date_applied, team=team, user_id=user_id
            )
            if duplicates:
                form_data = SimpleNamespace(
                    job_desc=job_desc,
                    company=company,
                    team=team,
                    contact=request.form.get("contact", ""),
                    date_applied=date_applied,
                    status=request.form.get("status", "Select_Status"),
                    success_chance=request.form.get("success_chance", "0"),
                    link=request.form.get("link", ""),
                    cover_letter=1 if request.form.get("cover_letter") else 0,
                    resume=1 if request.form.get("resume") else 0,
                    comment=request.form.get("comment", ""),
                    additional_notes=request.form.get("additional_notes", ""),
                    job_expiry_date=request.form.get("job_expiry_date", ""),
                    industry=request.form.get("industry", ""),
                    ai_fit_score=None,
                    ai_fit_verdict=None,
                    ai_matching_skills=None,
                    ai_skill_gaps=None,
                    ai_recommendation=None,
                    last_modified_at=None,
                    last_contact_date=request.form.get("last_contact_date", ""),
                )
                return render_template(
                    "application_form.html",
                    app=form_data,
                    companies=db.get_companies(),
                    status_options=db.get_status_options(user_id=user_id),
                    action="Add",
                    duplicate_warning=True,
                    duplicates=duplicates,
                )

        db.add_application(request.form, user_id=user_id)
        flash("Application added.", "success")
        year = request.form.get("date_applied", "")[:4] or str(date.today().year)
        return redirect(url_for("dashboard.year_view", year=year))
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=None,
        companies=companies_list,
        status_options=db.get_status_options(user_id=user_id),
        action="Add",
    )


@bp.route("/application/edit/<int:app_id>", methods=["GET", "POST"])
@login_required
def edit_application(app_id):
    user_id = current_user_id()
    application = db.get_application(app_id, user_id=user_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        logger.info("edit_application: POST id=%s status=%s job_expiry_date=%s",
                    app_id,
                    request.form.get("status"),
                    request.form.get("job_expiry_date"))
        try:
            db.update_application(app_id, request.form)
        except Exception:
            logger.exception("edit_application: update_application raised for id=%s", app_id)
            raise
        flash("Application updated.", "success")
        year = request.form.get("date_applied", "")[:4] or str(date.today().year)
        return redirect(url_for("dashboard.year_view", year=year))
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=application,
        companies=companies_list,
        status_options=db.get_status_options(user_id=user_id),
        action="Edit",
    )


@bp.route("/application/delete/<int:app_id>", methods=["POST"])
@login_required
def delete_application(app_id):
    user_id = current_user_id()
    application = db.get_application(app_id, user_id=user_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    year = application["date_applied"][:4] if application else str(date.today().year)
    db.delete_application(app_id, user_id=user_id)
    flash("Application deleted.", "warning")
    return redirect(url_for("dashboard.year_view", year=year))


@bp.route("/applications/bulk-action", methods=["POST"])
@login_required
def bulk_action():
    """Handle bulk operations (delete / set-field) on multiple applications."""
    user_id = current_user_id()
    action        = request.form.get("action", "")
    year          = request.form.get("year", str(date.today().year))
    status_filter = request.form.get("status_filter", "")

    raw_ids = request.form.getlist("selected_ids")
    try:
        selected_ids = [int(x) for x in raw_ids if str(x).isdigit()]
    except ValueError:
        selected_ids = []

    redirect_kwargs: dict = {"year": year}
    if status_filter:
        redirect_kwargs["status"] = status_filter

    if not selected_ids:
        flash("No applications selected.", "warning")
        return redirect(url_for("dashboard.year_view", **redirect_kwargs))

    if action == "delete":
        count = db.bulk_delete_applications(selected_ids, user_id=user_id)
        flash(f"Deleted {count} application(s).", "warning")

    elif action == "set_status":
        new_status = request.form.get("bulk_status", "").strip()
        if not new_status:
            flash("Please choose a status.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "status", new_status, user_id=user_id)
            flash(
                f"Status set to '{new_status.replace('_', ' ')}' "
                f"for {count} application(s).",
                "success",
            )

    elif action == "set_date_applied":
        new_date = request.form.get("bulk_date_applied", "").strip()
        if not new_date:
            flash("Please enter a date.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "date_applied", new_date, user_id=user_id)
            flash(f"Date Applied set to {new_date} for {count} application(s).", "success")

    elif action == "set_last_contact":
        new_date = request.form.get("bulk_last_contact", "").strip()
        if not new_date:
            flash("Please enter a date.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "last_contact_date", new_date, user_id=user_id)
            flash(f"Last Contact set to {new_date} for {count} application(s).", "success")

    elif action == "set_cover_letter":
        value = 1 if request.form.get("bulk_cover_letter") == "1" else 0
        label = "Yes" if value else "No"
        count = db.bulk_update_applications(selected_ids, "cover_letter", value, user_id=user_id)
        flash(f"Cover Letter set to {label} for {count} application(s).", "success")

    elif action == "set_resume":
        value = 1 if request.form.get("bulk_resume") == "1" else 0
        label = "Yes" if value else "No"
        count = db.bulk_update_applications(selected_ids, "resume", value, user_id=user_id)
        flash(f"Resume set to {label} for {count} application(s).", "success")

    else:
        flash("Unknown bulk action.", "warning")

    return redirect(url_for("dashboard.year_view", **redirect_kwargs))

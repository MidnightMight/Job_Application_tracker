"""Application CRUD and bulk-action routes."""

import logging
import os
import re
from datetime import date
from types import SimpleNamespace

from flask import (
    Blueprint, abort, flash, redirect, render_template,
    request, send_file, session, url_for,
)

import db
from .auth import _safe_path, login_required, current_user_id
from db.applications import _STALE_DAYS

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
        attachments=db.get_attachments(app_id),
        attachment_kinds=db.ATTACHMENT_KINDS,
        attachment_types=", ".join(sorted(db.ALLOWED_EXTENSIONS)),
    )


def _form_values(source) -> SimpleNamespace:
    """Values to show in the add form, from a submitted form or a shared link."""
    return SimpleNamespace(
        job_desc=source.get("job_desc", ""),
        company=source.get("company", ""),
        team=source.get("team", ""),
        contact=source.get("contact", ""),
        how_applied=source.get("how_applied", ""),
        employer_contact=source.get("employer_contact", ""),
        date_applied=source.get("date_applied", ""),
        status=source.get("status", "Select_Status"),
        success_chance=source.get("success_chance", "0"),
        link=source.get("link", ""),
        cover_letter=1 if source.get("cover_letter") else 0,
        resume=1 if source.get("resume") else 0,
        comment=source.get("comment", ""),
        additional_notes=source.get("additional_notes", ""),
        job_expiry_date=source.get("job_expiry_date", ""),
        industry=source.get("industry", ""),
        next_action=source.get("next_action", ""),
        next_action_date=source.get("next_action_date", ""),
        job_ad_text=source.get("job_ad_text", ""),
        priority=db.parse_priority(source.get("priority")) or 0,
        ai_fit_score=None,
        ai_fit_verdict=None,
        ai_matching_skills=None,
        ai_skill_gaps=None,
        ai_recommendation=None,
        last_modified_at=None,
        last_contact_date=source.get("last_contact_date", ""),
    )


_URL_RE = re.compile(r"https?://\S+")


@bp.route("/share")
def share():
    """PWA share target: a job ad shared from the phone opens the add form.

    Not behind login_required on purpose: it only stashes the shared link and
    title in the session, so the add form (which is) can pick them up even
    when the user has to log in first.
    """
    title = request.args.get("title", "").strip()
    text = request.args.get("text", "").strip()
    link = request.args.get("url", "").strip()
    if not link.startswith(("http://", "https://")):
        # Many apps put the link in the text instead of the url field.
        found = _URL_RE.search(text) or _URL_RE.search(title)
        link = found.group(0) if found else ""
    if link:
        title = title.replace(link, "").strip()
    session["share_prefill"] = {"link": link[:2000], "job_desc": title[:200]}
    return redirect(url_for("applications.add_application"))


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
                company, job_desc, date_applied, team=team, user_id=user_id,
                link=request.form.get("link", ""),
            )
            if duplicates:
                return render_template(
                    "application_form.html",
                    app=_form_values(request.form),
                    companies=db.get_companies(),
                    status_options=db.get_status_options(user_id=user_id),
                    action="Add",
                    duplicate_warning=True,
                    duplicates=duplicates,
                    duplicate_window_days=db.DUPLICATE_WINDOW_DAYS,
                    stale_days=_STALE_DAYS,
                )

        db.add_application(request.form, user_id=user_id)
        flash("Application added.", "success")
        year = request.form.get("date_applied", "")[:4] or str(date.today().year)
        return redirect(url_for("dashboard.year_view", year=year))
    prefill = None
    shared = session.pop("share_prefill", None)
    if shared:
        prefill = _form_values({**shared, "resume": 1})
        same_link = [d for d in db.find_duplicate_applications(
            "", "", "", user_id=user_id, link=shared.get("link", "")) if d["reason"] == "link"]
        if same_link:
            flash(f"You already have this job saved: {same_link[0]['company']} "
                  f"({same_link[0]['status'].replace('_', ' ')}).", "warning")
        else:
            flash("Job link added from your share. Fill in the rest, or paste the ad into AI fill.", "info")
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=prefill,
        companies=companies_list,
        status_options=db.get_status_options(user_id=user_id),
        action="Add",
        stale_days=_STALE_DAYS,
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
        stale_days=_STALE_DAYS,
    )


@bp.route("/application/delete/<int:app_id>", methods=["POST"])
@login_required
def delete_application(app_id):
    user_id = current_user_id()
    application = db.get_application(app_id, user_id=user_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    year = (application.get("date_applied") or "")[:4] or str(date.today().year)
    db.delete_application(app_id, user_id=user_id)
    flash("Application deleted.", "warning")
    return redirect(url_for("dashboard.year_view", year=year))


@bp.route("/application/archive/<int:app_id>", methods=["POST"])
@login_required
def archive_application(app_id):
    user_id = current_user_id()
    application = db.get_application(app_id, user_id=user_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    allowed = {"Rejected", "Not_Applying", "Job_Expired"}
    if application.get("status") not in allowed:
        flash("Only Rejected, Not Applying, or Job Expired applications can be archived.", "warning")
        year = application["date_applied"][:4] if application.get("date_applied") else str(date.today().year)
        return redirect(url_for("dashboard.year_view", year=year))

    db.archive_application(app_id, user_id=user_id)
    flash("Application archived.", "success")
    year = application["date_applied"][:4] if application.get("date_applied") else str(date.today().year)
    return redirect(url_for("dashboard.year_view", year=year))


@bp.route("/application/<int:app_id>/priority", methods=["POST"])
@login_required
def set_priority(app_id):
    level = db.parse_priority(request.form.get("priority", ""))
    if level is None or not db.set_priority(app_id, level, user_id=current_user_id()):
        flash("Couldn't change the priority.", "danger")
    back = _safe_path(request.form.get("next", ""))
    return redirect(back or url_for("applications.application_detail", app_id=app_id))


@bp.route("/application/unarchive/<int:app_id>", methods=["POST"])
@login_required
def unarchive_application(app_id):
    user_id = current_user_id()
    if not db.unarchive_application(app_id, user_id=user_id):
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    flash("Application restored from the archive.", "success")
    back = _safe_path(request.form.get("next", ""))
    return redirect(back or url_for("applications.application_detail", app_id=app_id))


@bp.route("/applications/bulk-action", methods=["POST"])
@login_required
def bulk_action():
    """Handle bulk operations (delete / set-field) on multiple applications."""
    user_id = current_user_id()
    action        = request.form.get("action", "")
    year          = request.form.get("year", str(date.today().year))
    status_filter = request.form.get("status_filter", "")
    sort_mode = request.form.get("sort_mode", "").strip().lower()

    raw_ids = request.form.getlist("selected_ids")
    try:
        selected_ids = [int(x) for x in raw_ids if str(x).isdigit()]
    except ValueError:
        selected_ids = []

    redirect_kwargs: dict = {"year": year}
    if status_filter:
        redirect_kwargs["status"] = status_filter
    if sort_mode in {"priority", "date", "status"}:
        redirect_kwargs["sort"] = sort_mode

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

    elif action == "set_priority":
        level = db.parse_priority(request.form.get("bulk_priority", ""))
        if level is None:
            flash("Please choose a priority.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "priority", level, user_id=user_id)
            label = db.PRIORITY_LEVELS.get(level, "Not set")
            flash(f"Priority set to {label} for {count} application(s).", "success")

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


# ── Attachments ──────────────────────────────────────────────────────────────

@bp.route("/application/<int:app_id>/attachments", methods=["POST"])
@login_required
def upload_attachment(app_id):
    user_id = current_user_id()
    if not db.get_application(app_id, user_id=user_id):
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    back = redirect(url_for("applications.application_detail", app_id=app_id) + "#attachments")
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Choose a file to attach.", "warning")
        return back
    filename = os.path.basename(upload.filename.replace("\\", "/")).strip() or "file"
    if os.path.splitext(filename)[1].lower() not in db.ALLOWED_EXTENSIONS:
        flash("That type of file can't be attached. Use "
              + ", ".join(sorted(db.ALLOWED_EXTENSIONS)) + ".", "danger")
        return back
    data = upload.read(db.MAX_ATTACHMENT_BYTES + 1)
    if len(data) > db.MAX_ATTACHMENT_BYTES:
        flash("That file is too big. Attachments can be up to 10 MB.", "danger")
        return back
    if not data:
        flash("That file is empty.", "warning")
        return back
    db.add_attachment(app_id, filename, data, kind=request.form.get("kind", ""))
    flash(f"Attached {filename}.", "success")
    return back


@bp.route("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    attachment = db.get_attachment(attachment_id, user_id=current_user_id())
    if not attachment:
        abort(404)
    path = db.attachment_path(attachment["stored_name"])
    if not os.path.exists(path):
        flash("That file is missing from the server (it may predate a database restore).", "warning")
        return redirect(url_for("applications.application_detail", app_id=attachment["application_id"]))
    return send_file(path, download_name=attachment["filename"], as_attachment=True)


@bp.route("/attachments/<int:attachment_id>/delete", methods=["POST"])
@login_required
def delete_attachment(attachment_id):
    attachment = db.get_attachment(attachment_id, user_id=current_user_id())
    if not attachment:
        abort(404)
    db.delete_attachment(attachment_id, user_id=current_user_id())
    flash(f"Removed {attachment['filename']}.", "warning")
    return redirect(url_for("applications.application_detail",
                            app_id=attachment["application_id"]) + "#attachments")

"""Dashboard, search, and year-view routes."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

import db
from .auth import login_required, current_user_id
from db.applications import _STALE_DAYS

bp = Blueprint("dashboard", __name__)
# Keep unknown statuses at the end of status-sorted lists.
_UNKNOWN_STATUS_SORT_ORDER = 10_000


@bp.route("/")
@login_required
def dashboard():
    user_id = current_user_id()
    current_year = date.today().year
    stats = db.get_stats(year=current_year, user_id=user_id)
    raw_status_counts = db.get_status_counts(year=current_year, user_id=user_id)
    ordered_statuses = db.get_status_options(user_id=user_id)
    status_counts = {
        s: raw_status_counts[s] for s in ordered_statuses if raw_status_counts.get(s, 0) > 0
    }
    for s, count in raw_status_counts.items():
        if s not in status_counts and count > 0:
            status_counts[s] = count
    apps_per_year = db.get_apps_per_year(user_id=user_id)
    success_per_year = db.get_success_rate_per_year(user_id=user_id)
    keyword_freq = db.get_company_note_frequency(user_id=user_id)
    attention_apps = db.get_attention_applications(user_id=user_id)
    return render_template(
        "dashboard.html",
        stats=stats,
        status_counts=status_counts,
        apps_per_year=apps_per_year,
        success_per_year=success_per_year,
        keyword_freq=keyword_freq,
        attention_apps=attention_apps,
        current_year=current_year,
        years=db.get_dynamic_years(user_id=user_id),
    )


@bp.route("/dashboard/attention/snooze/<int:app_id>", methods=["POST"])
@login_required
def snooze_attention(app_id):
    user_id = current_user_id()
    app = db.get_application(app_id, user_id=user_id)
    if not app:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    try:
        hours = int(request.form.get("hours", "1"))
    except (TypeError, ValueError):
        hours = 1
    hours = max(0, min(72, hours))
    db.set_attention_snooze(app_id, hours, user_id=user_id)
    if hours == 0:
        flash("Attention snooze cleared.", "info")
    else:
        flash(f"Attention snoozed for {hours} hour(s).", "success")
    return redirect(url_for("dashboard.dashboard"))


@bp.route("/search")
@login_required
def search():
    user_id = current_user_id()
    query = request.args.get("q", "").strip()
    results = []
    if len(query) >= 2:
        results = db.search_applications(query, user_id=user_id)
    return render_template("search.html", query=query, results=results)


@bp.route("/year/<int:year>")
@login_required
def year_view(year):
    user_id = current_user_id()
    status_filter = request.args.get("status", "")
    default_sort = db.get_setting("applications_default_sort", "status").strip().lower()
    if default_sort not in {"date", "status"}:
        default_sort = "status"
    sort_mode = request.args.get("sort", default_sort).strip().lower()
    status_options = db.get_status_options(user_id=user_id)
    apps = db.get_applications(
        year=year,
        status=status_filter if status_filter else None,
        user_id=user_id,
    )
    if sort_mode == "status":
        order = {name: i for i, name in enumerate(status_options)}
        apps.sort(
            key=lambda a: (
                order.get(a["status"], _UNKNOWN_STATUS_SORT_ORDER),
                a.get("date_applied") or "",
                a.get("company") or "",
            )
        )
    else:
        sort_mode = "date"
    stats = db.get_stats(year=year, user_id=user_id)
    return render_template(
        "year_view.html",
        apps=apps,
        year=year,
        stats=stats,
        status_counts=db.get_status_counts(year=year, user_id=user_id),
        years=db.get_dynamic_years(user_id=user_id),
        status_options=status_options,
        selected_status=status_filter,
        sort_mode=sort_mode,
        stale_days=_STALE_DAYS,
    )


@bp.route("/assistant")
@login_required
def assistant():
    user_id = current_user_id()
    ai_available = db.user_has_own_ai(user_id) or db.get_setting("ollama_enabled", "0") == "1"
    if not ai_available:
        flash("O.t.t.o is unavailable because AI is not enabled.", "warning")
        return redirect(url_for("dashboard.dashboard"))
    return render_template("assistant_chat.html")

"""Dashboard, search, and year-view routes."""

from datetime import date

from flask import Blueprint, render_template, request

import db
from .auth import login_required, current_user_id
from db.applications import _STALE_DAYS

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def dashboard():
    user_id = current_user_id()
    current_year = date.today().year
    stats = db.get_stats(year=current_year, user_id=user_id)
    status_counts = db.get_status_counts(year=current_year, user_id=user_id)
    apps_per_year = db.get_apps_per_year(user_id=user_id)
    success_per_year = db.get_success_rate_per_year(user_id=user_id)
    keyword_freq = db.get_company_note_frequency(user_id=user_id)
    return render_template(
        "dashboard.html",
        stats=stats,
        status_counts=status_counts,
        apps_per_year=apps_per_year,
        success_per_year=success_per_year,
        keyword_freq=keyword_freq,
        current_year=current_year,
        years=db.get_dynamic_years(user_id=user_id),
    )


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
    sort_mode = request.args.get("sort", "date").strip().lower()
    status_options = db.get_status_options(user_id=user_id)
    apps = db.get_applications(
        year=year,
        status=status_filter if status_filter else None,
        user_id=user_id,
    )
    if sort_mode == "status":
        order = {name: i for i, name in enumerate(status_options)}
        apps.sort(key=lambda a: (order.get(a["status"], 10_000), a.get("date_applied") or "", a.get("company") or ""))
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

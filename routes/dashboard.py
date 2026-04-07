"""Dashboard, search, and year-view routes."""

from flask import Blueprint, render_template, request

import db
from .auth import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def dashboard():
    current_year = 2025
    stats = db.get_stats(year=current_year)
    status_counts = db.get_status_counts(year=current_year)
    apps_per_year = db.get_apps_per_year()
    success_per_year = db.get_success_rate_per_year()
    keyword_freq = db.get_company_note_frequency()
    return render_template(
        "dashboard.html",
        stats=stats,
        status_counts=status_counts,
        apps_per_year=apps_per_year,
        success_per_year=success_per_year,
        keyword_freq=keyword_freq,
        current_year=current_year,
        years=db.get_dynamic_years(),
    )


@bp.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()
    results = []
    if len(query) >= 2:
        results = db.search_applications(query)
    return render_template("search.html", query=query, results=results)


@bp.route("/year/<int:year>")
def year_view(year):
    status_filter = request.args.get("status", "")
    apps = db.get_applications(
        year=year,
        status=status_filter if status_filter else None,
    )
    stats = db.get_stats(year=year)
    return render_template(
        "year_view.html",
        apps=apps,
        year=year,
        stats=stats,
        years=db.get_dynamic_years(),
        status_options=db.get_status_options(),
        selected_status=status_filter,
    )

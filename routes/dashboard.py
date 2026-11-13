"""Dashboard, search, and year-view routes."""

from datetime import date

from flask import Blueprint, render_template, request

import db
from .auth import login_required, current_user_id
from db.applications import applied_stale_days

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
    # The status board counts every application this year, archived ones too, in the
    # user's status order (unknown statuses last).  Each cell also knows how many of
    # its applications are archived, so its link can open the right view.
    board_counts = db.get_status_counts(year=current_year, user_id=user_id, include_archived=True)
    archived_counts = {s: board_counts[s] - status_counts.get(s, 0) for s in board_counts}
    order = db.get_status_options(user_id=user_id)
    statuses = [s for s in order if s in board_counts] + [s for s in board_counts if s not in order]
    pipeline = [(s, board_counts[s], archived_counts[s]) for s in statuses]
    return render_template(
        "dashboard.html",
        stats=stats,
        status_counts=status_counts,
        pipeline=pipeline,
        apps_per_year=apps_per_year,
        success_per_year=success_per_year,
        keyword_freq=keyword_freq,
        upcoming=db.get_upcoming_actions(user_id=user_id),
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
    sort_mode = request.args.get("sort", "status").strip().lower()
    status_options = db.get_status_options(user_id=user_id)
    show = request.args.get("show", "")
    if status_filter == db.EOI_STATUS and show != "archived":
        show = "eoi"                     # picking EOI in the status filter opens its view
    show_archived = show == "archived"
    show_eoi = show == "eoi"
    show_stale = show == "stale"
    everything = db.get_applications(
        year=year,
        status=status_filter if status_filter else None,
        user_id=user_id,
        include_archived=True,
    )
    archived_count = sum(1 for a in everything if a.get("archived"))
    eoi_count = sum(1 for a in everything if not a.get("archived") and a.get("status") == db.EOI_STATUS)
    stale_count = sum(1 for a in everything if a.get("is_stale"))
    if show_archived:
        apps = [a for a in everything if a.get("archived")]
    elif show_stale:
        apps = [a for a in everything if a.get("is_stale")]      # never archived, saved or EOI
    else:
        # Expressions of interest have their own view; the main list leaves them out.
        apps = [a for a in everything if not a.get("archived")
                and (a.get("status") == db.EOI_STATUS) == show_eoi]
    if sort_mode == "priority":
        apps = db.sort_by_priority(apps)
    elif sort_mode == "date":
        pass  # get_applications already returns newest first
    else:
        # Default: interviews and assessments first, then drafting, saved, applied, finished.
        sort_mode = "status"
        apps = db.sort_by_status(apps, status_options)
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
        stale_days=applied_stale_days(),
        show_archived=show_archived,
        archived_count=archived_count,
        show_eoi=show_eoi,
        eoi_count=eoi_count,
        show_stale=show_stale,
        stale_count=stale_count,
    )

"""Insights: which ways of applying, and which industries, get replies."""

from flask import Blueprint, render_template, request

import db
from .auth import login_required, current_user_id

bp = Blueprint("insights", __name__)


@bp.route("/insights")
@login_required
def insights():
    user_id = current_user_id()
    years = db.get_dynamic_years(user_id=user_id)
    year_arg = request.args.get("year", "")
    year = int(year_arg) if year_arg.isdigit() and int(year_arg) in years else None
    return render_template(
        "insights.html",
        insights=db.get_insights(year=year, user_id=user_id),
        flow=db.get_application_flow(year=year, user_id=user_id),
        year=year,
        years=years,
    )

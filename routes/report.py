"""Workforce Australia job search report: one fortnight of applications."""

import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

import db
from .auth import login_required, current_user_id

bp = Blueprint("report", __name__)

PERIOD_DAYS = 14

# Report columns: (heading, how to get the value from an application).
REPORT_COLUMNS = (
    ("Date applied",     lambda a: _au_date(a.get("date_applied"))),
    ("Job title",        lambda a: a.get("job_desc") or ""),
    ("Employer",         lambda a: a.get("company") or ""),
    ("How applied",      lambda a: a.get("how_applied") or ""),
    ("Employer contact", lambda a: a.get("employer_contact") or ""),
    ("Status",           lambda a: _status_text(a.get("status"))),
    ("Link",             lambda a: a.get("link") or ""),
)


def _au_date(value) -> str:
    """YYYY-MM-DD... -> DD/MM/YYYY (blank stays blank)."""
    try:
        return date.fromisoformat((value or "")[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return value or ""


def _status_text(status) -> str:
    """Status as words; the "Select_Status" placeholder (no status yet) is blank."""
    return "" if status in (None, "", "Select_Status") else status.replace("_", " ")


def _parse(value) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _anchor_key(user_id) -> str:
    """Settings key for the user's reporting-period start (each user has their own)."""
    return "wfa_period_start" if user_id is None else f"wfa_period_start:{user_id}"


def _period_start(user_id, today: date) -> tuple[date, bool]:
    """Start of the period to show, and whether the user has set their period.

    ?start= picks a period directly (prev/next links).  Otherwise it is the
    period containing today, counted in fortnights from the saved start date
    (or from this week's Monday if none is saved).
    """
    requested = _parse(request.args.get("start"))
    anchor = _parse(db.get_setting(_anchor_key(user_id), ""))
    if requested:
        return requested, anchor is not None
    if anchor is None:
        return today - timedelta(days=today.weekday()), False
    return anchor + timedelta(days=((today - anchor).days // PERIOD_DAYS) * PERIOD_DAYS), True


def _report_rows(start: date, user_id):
    end = start + timedelta(days=PERIOD_DAYS - 1)
    apps = db.get_applications_applied_between(start.isoformat(), end.isoformat(), user_id=user_id)
    return end, apps


@bp.route("/report/workforce", methods=["GET", "POST"])
@login_required
def workforce_report():
    user_id = current_user_id()
    if request.method == "POST":
        new_start = _parse(request.form.get("period_start"))
        if new_start is None:
            flash("Please pick the date your reporting period starts.", "warning")
        else:
            db.set_setting(_anchor_key(user_id), new_start.isoformat())
            flash("Reporting period saved.", "success")
        return redirect(url_for("report.workforce_report"))

    today = date.today()
    start, period_set = _period_start(user_id, today)
    end, apps = _report_rows(start, user_id)
    rows = [
        {
            "id": a["id"],
            "values": [get(a) for _, get in REPORT_COLUMNS],
            "missing": [label for label, key in (("how applied", "how_applied"),
                                                 ("employer contact", "employer_contact"))
                        if not (a.get(key) or "").strip()],
        }
        for a in apps
    ]
    return render_template(
        "workforce_report.html",
        columns=[label for label, _ in REPORT_COLUMNS],
        rows=rows,
        start=start,
        end=end,
        prev_start=start - timedelta(days=PERIOD_DAYS),
        next_start=start + timedelta(days=PERIOD_DAYS),
        is_current=start <= today <= end,
        period_set=period_set,
        saved_start=db.get_setting(_anchor_key(user_id), ""),
        missing_count=sum(1 for r in rows if r["missing"]),
    )


@bp.route("/report/workforce.csv")
@login_required
def workforce_report_csv():
    user_id = current_user_id()
    start, _ = _period_start(user_id, date.today())
    end, apps = _report_rows(start, user_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([label for label, _ in REPORT_COLUMNS])
    for a in apps:
        writer.writerow([get(a) for _, get in REPORT_COLUMNS])

    filename = f"workforce-report_{start.isoformat()}_to_{end.isoformat()}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

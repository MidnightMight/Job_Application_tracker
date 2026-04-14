"""Statistics helpers."""

from datetime import date

from .connection import get_connection, get_dynamic_years
from .init_db import PENDING_STATUSES

# Statuses that have NOT yet been submitted (or will never be submitted).
# Applications in any of these states are excluded from the "submitted" count.
_NON_SUBMITTED_STATUSES = {
    "Select_Status",
    "Drafting_Application",
    "Drafting_CV",
    "Not_Applying",
    "Job_Expired",
    "EOI",
}


def get_stats(year=None, user_id=None):
    from .applications import get_applications
    apps = get_applications(year=year, user_id=user_id)
    total = len(apps)
    submitted = sum(
        1 for a in apps
        if a["status"] not in _NON_SUBMITTED_STATUSES
    )
    rejected = sum(1 for a in apps if "Rejected" in a["status"])
    offers = sum(1 for a in apps if a["status"] == "Offer_Received")
    success_rate = round((offers / submitted * 100), 1) if submitted else 0
    pending = [a for a in apps if a["status"] in PENDING_STATUSES]
    return {
        "total":        total,
        "submitted":    submitted,
        "rejected":     rejected,
        "offers":       offers,
        "success_rate": success_rate,
        "pending":      pending,
    }


def get_status_counts(year=None, user_id=None):
    from .applications import get_applications
    apps = get_applications(year=year, user_id=user_id)
    counts: dict = {}
    for a in apps:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return counts


def get_apps_per_year(user_id=None):
    """Return {year_str: count} for all years visible to user_id."""
    years = get_dynamic_years(user_id=user_id)
    conn = get_connection()
    sql = (
        "SELECT strftime('%Y', date_applied) as yr, COUNT(*) as cnt "
        "FROM applications WHERE date_applied IS NOT NULL"
    )
    params: list = []
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " GROUP BY yr ORDER BY yr"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = {str(y): 0 for y in years}
    for r in rows:
        if r["yr"] in result:
            result[r["yr"]] = r["cnt"]
    return result


def get_success_rate_per_year(user_id=None):
    from .applications import get_applications
    years = get_dynamic_years(user_id=user_id)
    result = {}
    for y in years:
        apps = get_applications(year=y, user_id=user_id)
        submitted = sum(
            1 for a in apps
            if a["status"] not in _NON_SUBMITTED_STATUSES
        )
        offers = sum(1 for a in apps if a["status"] == "Offer_Received")
        result[str(y)] = round((offers / submitted * 100), 1) if submitted else 0
    return result


def get_company_note_frequency(user_id=None):
    """Return top sectors/notes from the companies table."""
    conn = get_connection()
    if user_id is not None:
        rows = conn.execute(
            "SELECT note FROM companies WHERE note IS NOT NULL AND note != '' AND user_id=?",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT note FROM companies WHERE note IS NOT NULL AND note != ''"
        ).fetchall()
    conn.close()
    freq: dict = {}
    for r in rows:
        note = r["note"].strip()
        if note:
            freq[note] = freq.get(note, 0) + 1
    return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15])

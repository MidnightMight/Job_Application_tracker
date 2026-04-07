"""Statistics helpers."""

from datetime import date

from .connection import get_connection, YEARS
from .init_db import PENDING_STATUSES


def get_stats(year=None):
    from .applications import get_applications
    apps = get_applications(year=year)
    total = len(apps)
    submitted = sum(
        1 for a in apps
        if a["status"] not in ("Select_Status", "Drafting_CV", "Not_Applying")
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


def get_status_counts(year=None):
    from .applications import get_applications
    apps = get_applications(year=year)
    counts: dict = {}
    for a in apps:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return counts


def get_apps_per_year():
    conn = get_connection()
    rows = conn.execute(
        """SELECT strftime('%Y', date_applied) as yr, COUNT(*) as cnt
           FROM applications GROUP BY yr ORDER BY yr"""
    ).fetchall()
    conn.close()
    result = {str(y): 0 for y in YEARS}
    for r in rows:
        if r["yr"] in result:
            result[r["yr"]] = r["cnt"]
    return result


def get_success_rate_per_year():
    from .applications import get_applications
    result = {}
    for y in YEARS:
        apps = get_applications(year=y)
        submitted = sum(
            1 for a in apps
            if a["status"] not in ("Select_Status", "Drafting_CV", "Not_Applying")
        )
        offers = sum(1 for a in apps if a["status"] == "Offer_Received")
        result[str(y)] = round((offers / submitted * 100), 1) if submitted else 0
    return result


def get_company_note_frequency():
    """Return top sectors/notes from the companies table."""
    conn = get_connection()
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

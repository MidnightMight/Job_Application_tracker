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


# ── Insights: what is working ────────────────────────────────────────────────

# Reaching any of these means the employer replied (a rejection is a reply too).
RESPONSE_STATUSES = frozenset({
    "Online_Assessment", "Interview_Scheduled", "Interview_In_Person",
    "Offer_Received", "Offer_Rejected", "Rejected",
})
# Reaching any of these means the application got through the first screen.
PROGRESSED_STATUSES = frozenset({
    "Online_Assessment", "Interview_Scheduled", "Interview_In_Person",
    "Offer_Received", "Offer_Rejected",
})
NOT_RECORDED = "Not recorded"


def _median(values: list) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _rates(apps: list) -> dict:
    sent = len(apps)
    heard = sum(1 for a in apps if a["heard_back"])
    progressed = sum(1 for a in apps if a["progressed"])
    waits = [a["reply_days"] for a in apps if a["reply_days"] is not None]
    return {
        "sent":            sent,
        "heard_back":      heard,
        "progressed":      progressed,
        "heard_back_pct":  round(heard / sent * 100) if sent else 0,
        "progressed_pct":  round(progressed / sent * 100) if sent else 0,
        "median_reply_days": _median(waits),
    }


def _grouped(apps: list, keys_for) -> list:
    """Rates per group, biggest group first.  *keys_for* gives an app's groups."""
    groups: dict = {}
    for a in apps:
        for key in keys_for(a):
            groups.setdefault(key, []).append(a)
    rows = [{"name": name, **_rates(members)} for name, members in groups.items()]
    rows.sort(key=lambda r: (r["name"] == NOT_RECORDED, -r["sent"], r["name"].lower()))
    return rows


def _industry_tags(app: dict) -> list:
    tags = [t.strip() for t in (app.get("industry") or "").split(",") if t.strip()]
    # One count per distinct tag, case-insensitively, keeping the first spelling.
    seen: dict = {}
    for t in tags:
        seen.setdefault(t.lower(), t)
    return list(seen.values()) or [NOT_RECORDED]


def get_insights(year=None, user_id=None) -> dict:
    """Response rates for applications sent to employers.

    Archived applications are included — they are real history.  Whether an
    application got a reply comes from its status history, so one that had
    an interview and was later rejected counts as both heard back and
    progressed.  Reply time is days from date applied to the first reply
    status, as recorded (when the status was changed in the tracker); it is
    left out for applications added already in a reply status.
    """
    from .applications import get_applications

    apps = [a for a in get_applications(year=year, user_id=user_id, include_archived=True)
            if a["status"] not in _NON_SUBMITTED_STATUSES]
    if year:
        # get_applications also returns undated rows for a year; insights need a date.
        apps = [a for a in apps if (a.get("date_applied") or "")[:4] == str(year)]

    history: dict = {}
    if apps:
        ids = [a["id"] for a in apps]
        placeholders = ",".join("?" for _ in ids)
        conn = get_connection()
        rows = conn.execute(
            f"SELECT application_id, status, changed_at FROM status_history"
            f" WHERE application_id IN ({placeholders}) ORDER BY id",
            ids,
        ).fetchall()
        conn.close()
        for r in rows:
            history.setdefault(r["application_id"], []).append((r["status"], r["changed_at"]))

    for a in apps:
        seen = history.get(a["id"], []) + [(a["status"], None)]
        a["heard_back"] = any(s in RESPONSE_STATUSES for s, _ in seen)
        a["progressed"] = any(s in PROGRESSED_STATUSES for s, _ in seen)
        a["reply_days"] = None
        # Only a status change made after the application was added dates the reply:
        # one added (or imported) already at interview or rejected says nothing about
        # how long the employer took.
        changes = history.get(a["id"], [])[1:]
        first_reply = next((when for s, when in changes if s in RESPONSE_STATUSES), None)
        if first_reply and a.get("date_applied"):
            try:
                days = (date.fromisoformat(first_reply[:10])
                        - date.fromisoformat(a["date_applied"][:10])).days
                if days >= 0:
                    a["reply_days"] = days
            except ValueError:
                pass

    return {
        "overall":     _rates(apps),
        "by_channel":  _grouped(apps, lambda a: [(a.get("how_applied") or "").strip() or NOT_RECORDED]),
        "by_industry": _grouped(apps, _industry_tags)[:12],
    }

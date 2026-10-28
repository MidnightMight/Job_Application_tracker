"""Application CRUD, duplicate detection, and bulk import helpers."""

import json
import logging
from datetime import date, datetime

from .connection import get_connection, _BULK_UPDATE_FIELDS

logger = logging.getLogger(__name__)


# Statuses that are "done" — no stale warning for these.
_TERMINAL_STATUSES = frozenset({
    "Offer_Received",
    "Offer_Rejected",
    "Rejected",
    "Not_Applying",
    "Job_Expired",
    "Select_Status",
})

# Days with no status change before an application is flagged as stale.
_STALE_DAYS = 3


def _enrich(app: dict, stale_ignored_statuses: set[str] | None = None) -> dict:
    """Add computed fields: 'duration' (days since applied) and 'is_stale'."""
    today = date.today()

    # duration — days since date_applied (0 when not set)
    try:
        d = datetime.strptime(app["date_applied"], "%Y-%m-%d").date()
        app["duration"] = (today - d).days
    except Exception:
        app["duration"] = 0

    # is_stale — True when status has not changed in >= _STALE_DAYS days and
    # the application is not in a terminal state.
    app["is_stale"] = False
    if (
        app.get("status") not in _TERMINAL_STATUSES
        and app.get("status") not in (stale_ignored_statuses or set())
    ):
        ref = app.get("status_changed_at") or app.get("date_applied") or ""
        try:
            ref_date = datetime.fromisoformat(ref[:10]).date()
            app["is_stale"] = (today - ref_date).days >= _STALE_DAYS
        except Exception:
            pass
    return app


def _statuses_ignored_for_stale(user_id: int | None = None) -> set[str]:
    """Statuses in the Submitted→Rejected range (inclusive) are stale-ignored."""
    try:
        from .statuses import get_status_options

        ordered = get_status_options(user_id=user_id)
        submitted_idx = ordered.index("Submitted")
        rejected_idx = ordered.index("Rejected")
        start = min(submitted_idx, rejected_idx)
        end = max(submitted_idx, rejected_idx)
        return set(ordered[start:end + 1])
    except ValueError:
        logger.debug(
            "_statuses_ignored_for_stale: Submitted or Rejected missing for user_id=%s",
            user_id,
        )
        return set()
    except ImportError:
        logger.debug("_statuses_ignored_for_stale: could not import get_status_options")
        return set()
    except Exception:
        logger.exception("_statuses_ignored_for_stale: unexpected error")
        return set()


def get_applications(year=None, status=None, user_id=None, include_archived: bool = False) -> list:
    conn = get_connection()
    sql = "SELECT * FROM applications WHERE 1=1"
    params: list = []
    if not include_archived:
        sql += " AND COALESCE(archived, 0) = 0"
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    if year:
        # Include matching year AND undated applications (no date_applied set yet)
        sql += (
            " AND (strftime('%Y', date_applied) = ?"
            " OR date_applied IS NULL OR date_applied = '')"
        )
        params.append(str(year))
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    stale_ignored = _statuses_ignored_for_stale(user_id=user_id)
    enriched = [_enrich(dict(r), stale_ignored) for r in rows]
    # Stale applications float to the top so they get immediate attention.
    enriched.sort(key=lambda a: (0 if a["is_stale"] else 1, a.get("date_applied") or ""))
    return enriched


# Choices for "How applied" on the form.  Stored as the text shown, so exports
# and the Workforce Australia report read naturally.  Imports keep any text.
HOW_APPLIED_OPTIONS = (
    "Online (job board)",
    "Company website",
    "Email",
    "In person",
    "Phone",
    "Recruitment agency",
    "Other",
)


def get_applications_applied_between(start: str, end: str, user_id=None) -> list:
    """Applications with a date applied from *start* to *end* (YYYY-MM-DD, inclusive).

    Archived applications are included: they were still applied for in that
    period.  Oldest first, as a job search report lists them.
    """
    conn = get_connection()
    sql = ("SELECT * FROM applications"
           " WHERE substr(date_applied, 1, 10) BETWEEN ? AND ?")
    params: list = [start, end]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY substr(date_applied, 1, 10), id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_applications(query: str, year: int | None = None, user_id=None, include_archived: bool = False) -> list:
    """Search applications across company, role, team, comment, notes, and contact."""
    conn = get_connection()
    like_pattern = f"%{query}%"
    sql = """
        SELECT * FROM applications
        WHERE (
            company          LIKE ? OR
            job_desc         LIKE ? OR
            team             LIKE ? OR
            comment          LIKE ? OR
            additional_notes LIKE ? OR
            contact          LIKE ?
        )
    """
    params: list = [like_pattern] * 6
    if not include_archived:
        sql += " AND COALESCE(archived, 0) = 0"
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    if year:
        sql += " AND strftime('%Y', date_applied) = ?"
        params.append(str(year))
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    stale_ignored = _statuses_ignored_for_stale(user_id=user_id)
    return [_enrich(dict(r), stale_ignored) for r in rows]


def get_application(app_id: int, user_id=None):
    """Fetch a single application.  When user_id is given, only returns the
    application if it belongs to that user (ownership check)."""
    conn = get_connection()
    if user_id is not None:
        row = conn.execute(
            "SELECT * FROM applications WHERE id=? AND user_id=?", (app_id, user_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM applications WHERE id=?", (app_id,)
        ).fetchone()
    conn.close()
    return _enrich(dict(row)) if row else None


def get_application_timeline(app_id: int) -> list:
    """Return status history entries for a single application, oldest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, changed_at FROM status_history "
        "WHERE application_id=? ORDER BY changed_at ASC",
        (app_id,),
    ).fetchall()
    conn.close()
    history = [dict(r) for r in rows]
    for i, entry in enumerate(history):
        if i == 0:
            entry["days_since_prev"] = None
        else:
            try:
                prev = datetime.fromisoformat(history[i - 1]["changed_at"])
                curr = datetime.fromisoformat(entry["changed_at"])
                entry["days_since_prev"] = (curr - prev).days
            except Exception:
                entry["days_since_prev"] = None
    return history


# Priority: 0 = not set, then Low / Medium / High.
PRIORITY_LEVELS = {3: "High", 2: "Medium", 1: "Low"}
_PRIORITY_WORDS = {"high": 3, "h": 3, "medium": 2, "med": 2, "m": 2, "low": 1, "l": 1,
                   "none": 0, "": 0}


def parse_priority(value) -> int | None:
    """0–3 from a number or High/Medium/Low; None when it can't be read."""
    if value is None:
        return 0
    text = str(value).strip().lower()
    if text in _PRIORITY_WORDS:
        return _PRIORITY_WORDS[text]
    try:
        number = int(float(text))
    except ValueError:
        return None
    return number if 0 <= number <= 3 else None


def sort_by_priority(apps: list) -> list:
    """Work still in progress first, highest priority first, then the soonest
    next step, then the newest application."""
    def key(a):
        finished = a.get("status") in ARCHIVABLE_STATUSES
        return (finished, -(a.get("priority") or 0), a.get("next_action_date") or "9999-99-99")
    newest_first = sorted(apps, key=lambda a: a.get("date_applied") or "", reverse=True)
    return sorted(newest_first, key=key)


def set_priority(app_id: int, priority: int, user_id=None) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    sql = "UPDATE applications SET priority=?, last_modified_at=? WHERE id=?"
    params: list = [priority, now, app_id]
    if user_id is not None:
        sql += " AND user_id=?"
        params.append(user_id)
    conn = get_connection()
    changed = conn.execute(sql, params).rowcount > 0
    conn.commit()
    conn.close()
    return changed


def add_application(data, user_id=None) -> int:
    """Insert a new application and return its ID.

    Also auto-creates the company record if it does not already exist.
    Sets last_modified_at to now.  user_id associates the record with the
    logged-in user; pass None in single-user (login-disabled) mode.
    """
    from .companies import _auto_add_or_update_company

    now = datetime.now().isoformat(timespec="seconds")
    company = data.get("company", "")
    industry = data.get("industry", "") or None

    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO applications
           (job_desc, team, company, date_applied, status,
            cover_letter, resume, comment, success_chance, link,
            contact, additional_notes, status_changed_at, last_contact_date,
            last_modified_at, job_expiry_date, industry, user_id,
            how_applied, employer_contact, next_action, next_action_date,
            job_ad_text, priority)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data.get("job_desc", ""),
            data.get("team", ""),
            company,
            data.get("date_applied", ""),
            data.get("status", "Select_Status"),
            1 if data.get("cover_letter") else 0,
            1 if data.get("resume") else 0,
            data.get("comment", ""),
            float(data.get("success_chance", 0) or 0),
            data.get("link", ""),
            data.get("contact", ""),
            data.get("additional_notes", ""),
            now,
            data.get("last_contact_date") or None,
            now,
            data.get("job_expiry_date") or None,
            industry,
            user_id,
            (data.get("how_applied") or "").strip(),
            (data.get("employer_contact") or "").strip(),
            (data.get("next_action") or "").strip(),
            data.get("next_action_date") or None,
            (data.get("job_ad_text") or "").strip(),
            parse_priority(data.get("priority")) or 0,
        ),
    )
    app_id = cur.lastrowid
    conn.execute(
        "INSERT INTO status_history (application_id, status, changed_at) VALUES (?,?,?)",
        (app_id, data.get("status", "Select_Status"), now),
    )
    conn.commit()
    conn.close()

    # Auto-create / update company record.
    _auto_add_or_update_company(
        company,
        industry,
        date_applied=data.get("date_applied", ""),
        status=data.get("status", "Select_Status"),
        app_id=app_id,
    )

    return app_id


def update_application(app_id: int, data):
    """Update an application record.

    Only sets last_modified_at when at least one field has actually changed.
    """
    logger.debug("update_application: id=%s status=%s job_expiry_date=%s industry=%s",
                 app_id,
                 data.get("status"),
                 data.get("job_expiry_date"),
                 data.get("industry"))

    from .companies import _auto_add_or_update_company

    now = datetime.now().isoformat(timespec="seconds")
    existing = get_application(app_id)
    if existing is None:
        logger.warning("update_application: application id=%s not found", app_id)

    new_status = data.get("status", "Select_Status")
    # Callers that don't send a priority keep the current one.
    if "priority" in data:
        new_priority = parse_priority(data.get("priority")) or 0
    else:
        new_priority = (existing or {}).get("priority") or 0

    # Detect whether any user-visible field changed.
    _changed = (
        existing is None
        or existing.get("job_desc",          "") != (data.get("job_desc",          "") or "")
        or existing.get("team",              "") != (data.get("team",              "") or "")
        or existing.get("company",           "") != (data.get("company",           "") or "")
        or existing.get("date_applied",      "") != (data.get("date_applied",      "") or "")
        or existing.get("status",  "Select_Status") != new_status
        or existing.get("cover_letter",       0) != (1 if data.get("cover_letter") else 0)
        or existing.get("resume",             1) != (1 if data.get("resume") else 0)
        or existing.get("comment",           "") != (data.get("comment",           "") or "")
        or float(existing.get("success_chance", 0) or 0) != float(data.get("success_chance", 0) or 0)
        or existing.get("link",              "") != (data.get("link",              "") or "")
        or existing.get("contact",           "") != (data.get("contact",           "") or "")
        or existing.get("additional_notes",  "") != (data.get("additional_notes",  "") or "")
        or existing.get("last_contact_date")     != (data.get("last_contact_date") or None)
        or existing.get("job_expiry_date")       != (data.get("job_expiry_date")   or None)
        or existing.get("industry")              != (data.get("industry")           or None)
        or (existing.get("how_applied")      or "") != (data.get("how_applied")      or "").strip()
        or (existing.get("employer_contact") or "") != (data.get("employer_contact") or "").strip()
        or (existing.get("next_action")      or "") != (data.get("next_action")      or "").strip()
        or existing.get("next_action_date")      != (data.get("next_action_date")  or None)
        or (existing.get("job_ad_text")      or "") != (data.get("job_ad_text")      or "").strip()
        or (existing.get("priority")          or 0) != new_priority
    )

    live_cols: list = []
    conn = get_connection()
    try:
        # Log the live schema so we can see if any expected column is missing
        live_cols = [r[1] for r in conn.execute("PRAGMA table_info(applications)").fetchall()]
        logger.debug("update_application: live applications columns = %s", live_cols)

        conn.execute(
            """UPDATE applications SET
               job_desc=?, team=?, company=?, date_applied=?, status=?,
               cover_letter=?, resume=?, comment=?, success_chance=?, link=?,
               contact=?, additional_notes=?, last_contact_date=?,
               job_expiry_date=?, industry=?, how_applied=?, employer_contact=?,
               next_action=?, next_action_date=?, job_ad_text=?, priority=?,
               status_changed_at=CASE WHEN status != ? THEN ? ELSE status_changed_at END,
               last_modified_at=CASE WHEN ? THEN ? ELSE last_modified_at END
               WHERE id=?""",
            (
                data.get("job_desc", ""),
                data.get("team", ""),
                data.get("company", ""),
                data.get("date_applied", ""),
                new_status,
                1 if data.get("cover_letter") else 0,
                1 if data.get("resume") else 0,
                data.get("comment", ""),
                float(data.get("success_chance", 0) or 0),
                data.get("link", ""),
                data.get("contact", ""),
                data.get("additional_notes", ""),
                data.get("last_contact_date") or None,
                data.get("job_expiry_date")   or None,
                data.get("industry")          or None,
                (data.get("how_applied")      or "").strip(),
                (data.get("employer_contact") or "").strip(),
                (data.get("next_action")      or "").strip(),
                data.get("next_action_date")  or None,
                (data.get("job_ad_text")      or "").strip(),
                new_priority,
                new_status,
                now,
                1 if _changed else 0,
                now,
                app_id,
            ),
        )
        if existing and existing.get("status") != new_status:
            conn.execute(
                "INSERT INTO status_history (application_id, status, changed_at) VALUES (?,?,?)",
                (app_id, new_status, now),
            )
        conn.commit()
        logger.debug("update_application: id=%s committed successfully", app_id)
    except Exception:
        logger.exception(
            "update_application: SQL failed for id=%s  live_cols=%s",
            app_id, live_cols,
        )
        raise
    finally:
        conn.close()

    _auto_add_or_update_company(
        data.get("company", ""),
        data.get("industry", "") or None,
        date_applied=data.get("date_applied", ""),
        status=new_status,
        app_id=app_id,
    )


def delete_application(app_id: int, user_id=None):
    from .attachments import remove_files_for_applications

    remove_files_for_applications([app_id], user_id=user_id)
    conn = get_connection()
    if user_id is not None:
        conn.execute("DELETE FROM applications WHERE id=? AND user_id=?", (app_id, user_id))
    else:
        conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
    conn.commit()
    conn.close()


def bulk_delete_applications(ids: list, user_id=None) -> int:
    """Delete multiple applications by ID. Returns the number of rows deleted.
    When user_id is given, only deletes applications owned by that user."""
    if not ids:
        return 0
    from .attachments import remove_files_for_applications

    remove_files_for_applications(ids, user_id=user_id)
    placeholders = ",".join("?" for _ in ids)
    conn = get_connection()
    if user_id is not None:
        conn.execute(
            f"DELETE FROM applications WHERE id IN ({placeholders}) AND user_id=?",
            (*ids, user_id),
        )
    else:
        conn.execute(f"DELETE FROM applications WHERE id IN ({placeholders})", ids)
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def bulk_update_applications(ids: list, field: str, value, user_id=None) -> int:
    """Set ``field`` to ``value`` for all application IDs in ``ids``.

    Security: ``field`` is validated against ``_BULK_UPDATE_FIELDS``;
    ``placeholders`` contains only literal '?' characters.
    When user_id is given, only updates applications owned by that user.
    Returns the number of rows updated.
    """
    if not ids:
        return 0
    if field not in _BULK_UPDATE_FIELDS:
        raise ValueError(f"bulk_update_applications: unknown field '{field}'")

    placeholders = ",".join("?" for _ in ids)
    user_filter = " AND user_id=?" if user_id is not None else ""
    user_params = [user_id] if user_id is not None else []
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()

    if field == "status":
        existing = {
            r["id"]: r["status"]
            for r in conn.execute(
                f"SELECT id, status FROM applications WHERE id IN ({placeholders}){user_filter}",
                (*ids, *user_params),
            ).fetchall()
        }
        conn.execute(
            f"UPDATE applications SET status=?, status_changed_at=? "
            f"WHERE id IN ({placeholders}){user_filter}",
            (value, now, *ids, *user_params),
        )
        for app_id in ids:
            if existing.get(app_id) != value:
                conn.execute(
                    "INSERT INTO status_history (application_id, status, changed_at) "
                    "VALUES (?,?,?)",
                    (app_id, value, now),
                )
    else:
        conn.execute(
            f"UPDATE applications SET {field}=? WHERE id IN ({placeholders}){user_filter}",
            (value, *ids, *user_params),
        )

    sync_rows = []
    if field in {"status", "date_applied"}:
        sync_rows = conn.execute(
            f"SELECT id, company, industry, date_applied, status "
            f"FROM applications WHERE id IN ({placeholders}){user_filter}",
            (*ids, *user_params),
        ).fetchall()

    count = conn.execute(
        f"SELECT COUNT(*) FROM applications WHERE id IN ({placeholders}){user_filter}",
        (*ids, *user_params),
    ).fetchone()[0]
    conn.commit()
    conn.close()

    # Keep company tracker in sync when status/date changes.
    if sync_rows:
        from .companies import _auto_add_or_update_company
        for r in sync_rows:
            _auto_add_or_update_company(
                r["company"],
                r["industry"],
                date_applied=r["date_applied"] or "",
                status=r["status"] or "",
                app_id=r["id"],
            )

    return count


def save_ai_fit(
    app_id: int,
    fit_score: int,
    verdict: str,
    matching_skills: list,
    skill_gaps: list,
    recommendation: str,
):
    """Persist AI fit analysis results to the application record."""
    conn = get_connection()
    conn.execute(
        """UPDATE applications SET
           ai_fit_score=?, ai_fit_verdict=?, ai_matching_skills=?,
           ai_skill_gaps=?, ai_recommendation=?
           WHERE id=?""",
        (
            fit_score,
            verdict,
            json.dumps(matching_skills),
            json.dumps(skill_gaps),
            recommendation,
            app_id,
        ),
    )
    conn.commit()
    conn.close()


def lower_success_chance_for_stale(app_id: int, max_chance: float = 0.1):
    """Reduce success_chance to at most *max_chance* for a likely-rejected application.

    Only decreases the value — if the user has already set a lower value it is
    left unchanged.  A NULL value is treated as 1.0 (100%) so it gets capped
    down to *max_chance*.  The WHERE guard avoids a no-op write when the value
    is already at or below the cap.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE applications"
        " SET success_chance = ?"
        " WHERE id = ? AND COALESCE(success_chance, 1.0) > ?",
        (max_chance, app_id, max_chance),
    )
    conn.commit()
    conn.close()


def archive_application(app_id: int, user_id=None) -> bool:
    """Mark an application as archived."""
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    if user_id is not None:
        cur = conn.execute(
            "UPDATE applications SET archived=1, archived_at=?, last_modified_at=? "
            "WHERE id=? AND user_id=?",
            (now, now, app_id, user_id),
        )
    else:
        cur = conn.execute(
            "UPDATE applications SET archived=1, archived_at=?, last_modified_at=? WHERE id=?",
            (now, now, app_id),
        )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def unarchive_application(app_id: int, user_id=None) -> bool:
    """Remove archive flag from an application.

    ``unarchived_at`` stops auto-archive from archiving it again straight away.
    """
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    if user_id is not None:
        cur = conn.execute(
            "UPDATE applications SET archived=0, archived_at=NULL, unarchived_at=?, last_modified_at=? "
            "WHERE id=? AND user_id=?",
            (now, now, app_id, user_id),
        )
    else:
        cur = conn.execute(
            "UPDATE applications SET archived=0, archived_at=NULL, unarchived_at=?, last_modified_at=? "
            "WHERE id=?",
            (now, now, app_id),
        )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def get_applications_for_company(company_name: str, user_id=None) -> dict:
    """Return all applications (active and archived) for a company, grouped by year.

    Returns a dict::

        {
            "active":   [<application dict>, …],   # archived=0, enriched
            "archived": [<application dict>, …],   # archived=1, enriched
            "by_year":  {year_str: {"active": [...], "archived": [...]}},
        }

    Both lists are sorted by year (descending) then date_applied (descending).
    ``user_id`` scopes the results to the logged-in user when login is enabled.
    """
    conn = get_connection()
    sql = (
        "SELECT * FROM applications "
        "WHERE LOWER(company) = ?"
    )
    params: list = [company_name.lower()]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    all_apps = [_enrich(dict(r)) for r in rows]

    active: list = []
    archived: list = []
    by_year: dict = {}

    for a in all_apps:
        year = (a.get("date_applied") or "")[:4] or "Undated"
        if year not in by_year:
            by_year[year] = {"active": [], "archived": []}
        if a.get("archived"):
            archived.append(a)
            by_year[year]["archived"].append(a)
        else:
            active.append(a)
            by_year[year]["active"].append(a)

    # Sort years descending (numeric, then "Undated" at end)
    sorted_by_year = {}
    for k in sorted(by_year.keys(), key=lambda y: (-int(y) if y.isdigit() else 1)):
        sorted_by_year[k] = by_year[k]

    return {"active": active, "archived": archived, "by_year": sorted_by_year}


def _dup_key(company: str, job_desc: str, team: str, date_applied: str) -> tuple:
    """Return a normalised key used to identify duplicate applications.

    The team field is included so that the same role at different teams
    is not considered a duplicate.
    """
    return (
        company.strip().lower(),
        job_desc.strip().lower(),
        (team or "").strip().lower(),
        date_applied,
    )


# Applying for the same company and role again within this many days is
# flagged as a possible duplicate when adding an application.
DUPLICATE_WINDOW_DAYS = 60


def find_duplicate_applications(
    company: str, job_desc: str, date_applied: str, team: str = "", user_id=None,
    link: str = "", window_days: int = DUPLICATE_WINDOW_DAYS,
) -> list[dict]:
    """Return existing applications that look like the one being added.

    A match is either the same job ad link, or the same company, role and team
    (case-insensitive, whitespace ignored) with a date applied within
    *window_days* of *date_applied*.  Undated applications only match other
    undated ones.  Different teams at the same company are NOT duplicates.
    Archived applications count: applying again after a rejection is worth
    knowing about.  When user_id is given, only that user's applications are
    searched.  Each result has a "reason" of "link" or "role".
    """
    company_key, role_key, team_key, date_key = _dup_key(company, job_desc, team, date_applied)
    link = (link or "").strip()
    conn = get_connection()
    sql = """SELECT id, company, job_desc, team, date_applied, status, archived,
                  CASE WHEN ? != '' AND TRIM(COALESCE(link, '')) = ? THEN 'link'
                       ELSE 'role' END AS reason
           FROM applications
           WHERE ((? != '' AND TRIM(COALESCE(link, '')) = ?)
              OR (LOWER(TRIM(company))  = ?
                  AND LOWER(TRIM(job_desc)) = ?
                  AND LOWER(TRIM(COALESCE(team, ''))) = ?
                  AND (COALESCE(date_applied, '') = ?
                       OR ABS(julianday(date_applied) - julianday(?)) <= ?)))"""
    params: list = [link, link, link, link, company_key, role_key, team_key,
                    date_key or "", date_key or None, window_days]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_actions(user_id=None, days: int = 14) -> list[dict]:
    """Applications with a next step due within *days* days, or already overdue.

    Soonest first.  Each gets "days_until" (negative when overdue).
    """
    conn = get_connection()
    sql = """SELECT * FROM applications
           WHERE COALESCE(archived, 0) = 0
             AND COALESCE(next_action_date, '') != ''
             AND julianday(next_action_date) <= julianday('now', 'localtime', 'start of day') + ?"""
    params: list = [days]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY next_action_date, company"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    today = date.today()
    result = []
    for r in rows:
        a = dict(r)
        try:
            a["days_until"] = (date.fromisoformat(a["next_action_date"][:10]) - today).days
        except ValueError:
            continue
        result.append(a)
    return result


def get_calendar_actions(user_id=None) -> list[dict]:
    """Every non-archived application with a next-step date, for the calendar feed."""
    conn = get_connection()
    sql = """SELECT id, company, job_desc, team, status, link, next_action,
                  next_action_date, last_modified_at
           FROM applications
           WHERE COALESCE(archived, 0) = 0 AND COALESCE(next_action_date, '') != ''"""
    params: list = []
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY next_action_date"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Statuses that may be archived, by hand or automatically.
ARCHIVABLE_STATUSES = ("Rejected", "Not_Applying", "Job_Expired")


def auto_archive_finished(days: int) -> int:
    """Archive applications that have sat in an archivable status for *days* days.

    The age is taken from the last status change (or the date applied when
    that is missing), or from when it was last restored from the archive if
    that is later.  Returns the number archived.
    """
    if days < 1:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    placeholders = ",".join("?" for _ in ARCHIVABLE_STATUSES)
    conn = get_connection()
    cur = conn.execute(
        f"""UPDATE applications SET archived=1, archived_at=?, last_modified_at=?
            WHERE COALESCE(archived, 0) = 0
              AND status IN ({placeholders})
              AND julianday('now', 'localtime')
                  - julianday(MAX(substr(COALESCE(NULLIF(status_changed_at, ''), date_applied), 1, 10),
                                  substr(COALESCE(unarchived_at, ''), 1, 10))) >= ?""",
        (now, now, *ARCHIVABLE_STATUSES, days),
    )
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


# ── Bulk import ──────────────────────────────────────────────────────────────

# Fields a CSV/Excel import may set.  Keys match the column names produced by
# the CSV export, so an exported file can be re-imported without remapping.
IMPORTABLE_FIELDS = (
    "company", "job_desc", "team", "date_applied", "status",
    "cover_letter", "resume", "success_chance", "link", "contact",
    "comment", "additional_notes", "industry", "job_expiry_date",
    "how_applied", "employer_contact", "next_action", "next_action_date",
    "job_ad_text", "priority",
)

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d")
_TRUE_VALUES = {"1", "true", "yes", "y", "x", "✓", "✔"}
_FALSE_VALUES = {"0", "false", "no", "n", ""}


def _parse_date(value: str) -> str | None:
    """Return *value* as YYYY-MM-DD, "" for blank, or None if unparseable.

    Accepts the common day-first and ISO formats, and ISO timestamps
    (e.g. "2026-10-26T12:00:00") by taking the date part.
    """
    value = (value or "").strip()
    if not value:
        return ""
    candidates = [value]
    if len(value) > 10 and value[4:5] == "-":
        candidates.append(value[:10])
    for candidate in candidates:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _parse_bool(value, default: int) -> int | None:
    """Return 1/0 for a yes/no style cell, *default* when missing, None if invalid."""
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return 1
    if text in _FALSE_VALUES:
        return 0
    return None


def _clean_import_row(row: dict, label: str, valid_statuses: set[str],
                      warnings: list[str]) -> dict:
    """Normalise one import row.  Only keys present in *row* are returned, so
    updates leave unmapped fields untouched.  Problems become warnings and the
    offending value falls back to a safe default."""
    out: dict = {}
    for key in IMPORTABLE_FIELDS:
        if key not in row:
            continue
        raw = row.get(key)
        value = raw.strip() if isinstance(raw, str) else raw

        if key in ("date_applied", "job_expiry_date", "next_action_date"):
            parsed = _parse_date(value or "")
            if parsed is None:
                warnings.append(f"{label}: could not read {key} '{value}' — left blank.")
                parsed = ""
            out[key] = parsed
        elif key in ("cover_letter", "resume"):
            default = 1 if key == "resume" else 0
            parsed = _parse_bool(value, default)
            if parsed is None:
                warnings.append(f"{label}: could not read {key} '{value}' — used {default}.")
                parsed = default
            out[key] = parsed
        elif key == "success_chance":
            try:
                out[key] = float(value) if value not in (None, "") else 0.0
            except (TypeError, ValueError):
                warnings.append(f"{label}: could not read success_chance '{value}' — used 0.")
                out[key] = 0.0
        elif key == "priority":
            parsed = parse_priority(value)
            if parsed is None:
                warnings.append(f"{label}: could not read priority '{value}' — left unset.")
                parsed = 0
            out[key] = parsed
        elif key == "status":
            if value and valid_statuses and value not in valid_statuses:
                warnings.append(f"{label}: unknown status '{value}' — set to Select_Status.")
                value = "Select_Status"
            out[key] = value or "Select_Status"
        else:
            out[key] = value or ""
    return out


def bulk_import_applications(rows: list[dict], user_id=None,
                             update_existing: bool = False) -> dict:
    """Import a list of dicts representing applications.

    * ``date_applied`` is optional — undated rows are imported as undated.
    * When *update_existing* is True, a row whose ``id`` matches one of the
      user's applications, or whose company + role + team + date matches an
      existing application, updates that application instead of being skipped.
      Only the mapped columns are changed.
    * Otherwise exact duplicates (company + role + team + date) are skipped.

    Returns {"imported", "updated", "skipped", "duplicates", "other_skipped",
    "errors", "warnings"}.  ``errors`` describes skipped rows; ``warnings``
    describes values that were corrected on rows that were still saved.
    """
    from .statuses import get_status_options

    try:
        valid_statuses = set(get_status_options(user_id=user_id))
    except Exception:  # pragma: no cover - defensive, statuses table missing
        logger.exception("bulk_import_applications: could not load statuses")
        valid_statuses = set()

    conn = get_connection()
    sql = (
        "SELECT id, LOWER(TRIM(company)), LOWER(TRIM(job_desc)), "
        "LOWER(TRIM(COALESCE(team,''))), COALESCE(date_applied,'') FROM applications"
    )
    params: list = []
    if user_id is not None:
        sql += " WHERE user_id=?"
        params.append(user_id)
    existing_rows = conn.execute(sql, params).fetchall()
    conn.close()
    existing_ids = {r[0] for r in existing_rows}
    existing_keys = {(r[1], r[2], r[3], r[4]): r[0] for r in existing_rows}

    imported = updated = duplicates = 0
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, start=1):
        company = (row.get("company") or "").strip()
        job_desc = (row.get("job_desc") or "").strip()
        label = f"Row {i} ({company or job_desc or 'blank'})"

        record = _clean_import_row(row, label, valid_statuses, warnings)

        target_id = None
        if update_existing:
            raw_id = str(row.get("id") or "").strip()
            if raw_id.isdigit() and int(raw_id) in existing_ids:
                target_id = int(raw_id)

        if target_id is None and not company and not job_desc:
            errors.append(f"Row {i}: either 'company' or 'job_desc' is required — row skipped.")
            continue

        lookup_key = _dup_key(company, job_desc, record.get("team", ""),
                              record.get("date_applied", ""))
        if target_id is None and lookup_key in existing_keys:
            if update_existing:
                target_id = existing_keys[lookup_key]
            else:
                errors.append(f"{label}: duplicate application already in database — row skipped.")
                duplicates += 1
                continue

        if target_id is not None:
            current = get_application(target_id, user_id=user_id)
            if current is None:
                errors.append(f"{label}: application id {target_id} not found — row skipped.")
                continue
            merged = {key: current.get(key) for key in IMPORTABLE_FIELDS}
            merged["last_contact_date"] = current.get("last_contact_date")
            merged.update(record)
            update_application(target_id, merged)
            updated += 1
            continue

        record.setdefault("status", "Select_Status")
        record.setdefault("resume", 1)
        new_id = add_application(record, user_id=user_id)
        existing_ids.add(new_id)
        existing_keys[lookup_key] = new_id
        imported += 1

    total_skipped = len(rows) - imported - updated
    return {
        "imported":      imported,
        "updated":       updated,
        "skipped":       total_skipped,
        "duplicates":    duplicates,
        "other_skipped": total_skipped - duplicates,
        "errors":        errors,
        "warnings":      warnings,
    }

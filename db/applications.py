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
            last_modified_at, job_expiry_date, industry, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
               job_expiry_date=?, industry=?,
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
    """Remove archive flag from an application."""
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    if user_id is not None:
        cur = conn.execute(
            "UPDATE applications SET archived=0, archived_at=NULL, last_modified_at=? "
            "WHERE id=? AND user_id=?",
            (now, app_id, user_id),
        )
    else:
        cur = conn.execute(
            "UPDATE applications SET archived=0, archived_at=NULL, last_modified_at=? WHERE id=?",
            (now, app_id),
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


def find_duplicate_applications(
    company: str, job_desc: str, date_applied: str, team: str = "", user_id=None
) -> list[dict]:
    """Return existing applications that match company, job_desc, team, and date_applied.

    Comparison is case-insensitive and ignores leading/trailing whitespace.
    Different teams at the same company on the same date are NOT duplicates.
    When user_id is given, only searches within that user's applications.
    """
    conn = get_connection()
    sql = """SELECT id, company, job_desc, team, date_applied, status
           FROM applications
           WHERE LOWER(TRIM(company))  = ?
             AND LOWER(TRIM(job_desc)) = ?
             AND LOWER(TRIM(COALESCE(team, ''))) = ?
             AND date_applied          = ?"""
    params = list(_dup_key(company, job_desc, team, date_applied))
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def bulk_import_applications(rows: list[dict], user_id=None) -> dict:
    """Import a list of dicts representing applications.

    Returns {"imported": int, "skipped": int, "duplicates": int,
             "other_skipped": int, "errors": list[str]}.
    Rows that are exact duplicates (company + job_desc + team + date) are skipped.
    When user_id is given, duplicates are checked and records created for that user.
    """
    conn = get_connection()
    sql = (
        "SELECT LOWER(TRIM(company)), LOWER(TRIM(job_desc)), "
        "LOWER(TRIM(COALESCE(team,''))), date_applied FROM applications"
    )
    params: list = []
    if user_id is not None:
        sql += " WHERE user_id=?"
        params.append(user_id)
    existing_rows = conn.execute(sql, params).fetchall()
    conn.close()
    existing_keys = {(r[0], r[1], r[2], r[3]) for r in existing_rows}

    imported = 0
    duplicates = 0
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        company = (row.get("company") or "").strip()
        job_desc = (row.get("job_desc") or "").strip()
        row_label = company or job_desc
        if not company and not job_desc:
            errors.append(
                f"Row {i}: either 'company' or 'job_desc' is required — row skipped."
            )
            continue
        date_applied = (row.get("date_applied") or "").strip()
        if not date_applied:
            errors.append(f"Row {i} ({row_label}): 'date_applied' is required — row skipped.")
            continue
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                date_applied = datetime.strptime(date_applied, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass
        team = (row.get("team") or "").strip()
        lookup_key = _dup_key(company, job_desc, team, date_applied)
        if lookup_key in existing_keys:
            errors.append(
                f"Row {i} ({row_label}): duplicate application already in database — row skipped."
            )
            duplicates += 1
            continue
        add_application({
            "job_desc":         job_desc,
            "team":             team,
            "company":          company,
            "date_applied":     date_applied,
            "status":           row.get("status", "Select_Status"),
            "cover_letter":     row.get("cover_letter", ""),
            "resume":           row.get("resume", "1"),
            "comment":          row.get("comment", ""),
            "success_chance":   row.get("success_chance", "0"),
            "link":             row.get("link", ""),
            "contact":          row.get("contact", ""),
            "additional_notes": row.get("additional_notes", ""),
            "industry":         row.get("industry", ""),
        }, user_id=user_id)
        existing_keys.add(lookup_key)
        imported += 1
    total_skipped = len(rows) - imported
    return {
        "imported":      imported,
        "skipped":       total_skipped,
        "duplicates":    duplicates,
        "other_skipped": total_skipped - duplicates,
        "errors":        errors,
    }

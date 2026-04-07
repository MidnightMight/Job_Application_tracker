"""Application CRUD, duplicate detection, and bulk import helpers."""

import json
from datetime import date, datetime

from .connection import get_connection, _BULK_UPDATE_FIELDS


def _enrich(app: dict) -> dict:
    """Add computed 'duration' field (days since applied)."""
    try:
        d = datetime.strptime(app["date_applied"], "%Y-%m-%d").date()
        app["duration"] = (date.today() - d).days
    except Exception:
        app["duration"] = 0
    return app


def get_applications(year=None, status=None) -> list:
    conn = get_connection()
    sql = "SELECT * FROM applications WHERE 1=1"
    params: list = []
    if year:
        sql += " AND strftime('%Y', date_applied) = ?"
        params.append(str(year))
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_enrich(dict(r)) for r in rows]


def search_applications(query: str, year: int | None = None) -> list:
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
    if year:
        sql += " AND strftime('%Y', date_applied) = ?"
        params.append(str(year))
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_enrich(dict(r)) for r in rows]


def get_application(app_id: int):
    conn = get_connection()
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


def add_application(data) -> int:
    """Insert a new application and return its ID.

    Also auto-creates the company record if it does not already exist.
    Sets last_modified_at to now.
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
            last_modified_at, job_expiry_date, industry)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
    _auto_add_or_update_company(company, industry)

    return app_id


def update_application(app_id: int, data):
    """Update an application record.

    Only sets last_modified_at when at least one field has actually changed.
    """
    now = datetime.now().isoformat(timespec="seconds")
    existing = get_application(app_id)
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

    conn = get_connection()
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
    conn.close()


def delete_application(app_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
    conn.commit()
    conn.close()


def bulk_delete_applications(ids: list) -> int:
    """Delete multiple applications by ID. Returns the number of rows deleted."""
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    conn = get_connection()
    conn.execute(f"DELETE FROM applications WHERE id IN ({placeholders})", ids)
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def bulk_update_applications(ids: list, field: str, value) -> int:
    """Set ``field`` to ``value`` for all application IDs in ``ids``.

    Security: ``field`` is validated against ``_BULK_UPDATE_FIELDS``;
    ``placeholders`` contains only literal '?' characters.
    Returns the number of rows updated.
    """
    if not ids:
        return 0
    if field not in _BULK_UPDATE_FIELDS:
        raise ValueError(f"bulk_update_applications: unknown field '{field}'")

    placeholders = ",".join("?" for _ in ids)
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()

    if field == "status":
        existing = {
            r["id"]: r["status"]
            for r in conn.execute(
                f"SELECT id, status FROM applications WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        }
        conn.execute(
            f"UPDATE applications SET status=?, status_changed_at=? "
            f"WHERE id IN ({placeholders})",
            (value, now, *ids),
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
            f"UPDATE applications SET {field}=? WHERE id IN ({placeholders})",
            (value, *ids),
        )

    count = conn.execute(
        f"SELECT COUNT(*) FROM applications WHERE id IN ({placeholders})", ids
    ).fetchone()[0]
    conn.commit()
    conn.close()
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
    company: str, job_desc: str, date_applied: str, team: str = ""
) -> list[dict]:
    """Return existing applications that match company, job_desc, team, and date_applied.

    Comparison is case-insensitive and ignores leading/trailing whitespace.
    Different teams at the same company on the same date are NOT duplicates.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, company, job_desc, team, date_applied, status
           FROM applications
           WHERE LOWER(TRIM(company))  = ?
             AND LOWER(TRIM(job_desc)) = ?
             AND LOWER(TRIM(COALESCE(team, ''))) = ?
             AND date_applied          = ?""",
        _dup_key(company, job_desc, team, date_applied),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def bulk_import_applications(rows: list[dict]) -> dict:
    """Import a list of dicts representing applications.

    Returns {"imported": int, "skipped": int, "duplicates": int,
             "other_skipped": int, "errors": list[str]}.
    Rows that are exact duplicates (company + job_desc + team + date) are skipped.
    """
    conn = get_connection()
    existing_rows = conn.execute(
        "SELECT LOWER(TRIM(company)), LOWER(TRIM(job_desc)), "
        "LOWER(TRIM(COALESCE(team,''))), date_applied FROM applications"
    ).fetchall()
    conn.close()
    existing_keys = {(r[0], r[1], r[2], r[3]) for r in existing_rows}

    imported = 0
    duplicates = 0
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        company = (row.get("company") or "").strip()
        if not company:
            errors.append(f"Row {i}: 'company' is required — row skipped.")
            continue
        date_applied = (row.get("date_applied") or "").strip()
        if not date_applied:
            errors.append(f"Row {i} ({company}): 'date_applied' is required — row skipped.")
            continue
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                date_applied = datetime.strptime(date_applied, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass
        job_desc = (row.get("job_desc") or "").strip()
        team = (row.get("team") or "").strip()
        lookup_key = _dup_key(company, job_desc, team, date_applied)
        if lookup_key in existing_keys:
            errors.append(
                f"Row {i} ({company}): duplicate application already in database — row skipped."
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
        })
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

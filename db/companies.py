"""Company CRUD helpers."""

from .connection import get_connection


_NON_COMPANY_TRACKING_STATUSES = {
    "Job_Expired",
    "Drafting_CV",
    "Select_Status",
    "Not_Applying",
}
_APPLIED_YEAR_COLUMNS = {f"applied_{y}" for y in range(2023, 2028)}


def _normalize_industry_tags(raw: str | None) -> str | None:
    """Normalise comma-separated industry tags into a deduplicated string."""
    if not raw:
        return None
    tags = []
    seen: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        tag = part.strip()
        key = tag.lower()
        if not tag or key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    return ", ".join(tags) if tags else None


def _merge_industry_tags(existing: str | None, incoming: str | None) -> str | None:
    """Merge two tag strings into one normalised comma-separated value."""
    left = _normalize_industry_tags(existing) or ""
    right = _normalize_industry_tags(incoming) or ""
    merged = ", ".join(x for x in (left, right) if x)
    return _normalize_industry_tags(merged)


def _should_track_company_year(status: str | None) -> bool:
    return (status or "") not in _NON_COMPANY_TRACKING_STATUSES


def get_companies(user_id: int | None = None, pool_enabled: bool = True):
    """Return companies visible to the given user.

    When pool_enabled is True (or login is not in use), all companies are
    returned regardless of owner.  When pool_enabled is False, only companies
    owned by user_id or with no owner (user_id IS NULL) are returned.

    In the pooled view the ``note`` (sector) of companies owned by OTHER users
    is blanked out so private annotations are not exposed across accounts.
    """
    conn = get_connection()
    rows = conn.execute("SELECT * FROM companies ORDER BY company_name").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        owner = d.get("user_id")
        if not pool_enabled and user_id is not None:
            if owner != user_id:
                continue
        if pool_enabled and user_id is not None and owner is not None and owner != user_id:
            d["note"] = None
            d["_pooled_from_other"] = True
        else:
            d["_pooled_from_other"] = False
        result.append(d)
    return result


def get_company(company_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM companies WHERE id=?", (company_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_company(data, user_id: int | None = None):
    industry_tags = _normalize_industry_tags(data.get("industry", ""))
    conn = get_connection()
    conn.execute(
        """INSERT INTO companies
           (company_name, note, applied_2023, applied_2024,
            applied_2025, applied_2026, applied_2027, user_id, industry)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            data.get("company_name", ""),
            data.get("note", ""),
            1 if data.get("applied_2023") else 0,
            1 if data.get("applied_2024") else 0,
            1 if data.get("applied_2025") else 0,
            1 if data.get("applied_2026") else 0,
            1 if data.get("applied_2027") else 0,
            user_id,
            industry_tags,
        ),
    )
    conn.commit()
    conn.close()


def update_company(company_id: int, data, user_id: int | None = None):
    industry_tags = _normalize_industry_tags(data.get("industry", ""))
    conn = get_connection()
    if user_id is not None:
        conn.execute(
            """UPDATE companies SET
               company_name=?, note=?,
               applied_2023=?, applied_2024=?, applied_2025=?,
               applied_2026=?, applied_2027=?, industry=?
               WHERE id=? AND user_id=?""",
            (
                data.get("company_name", ""),
                data.get("note", ""),
                1 if data.get("applied_2023") else 0,
                1 if data.get("applied_2024") else 0,
                1 if data.get("applied_2025") else 0,
                1 if data.get("applied_2026") else 0,
                1 if data.get("applied_2027") else 0,
                industry_tags,
                company_id,
                user_id,
            ),
        )
    else:
        conn.execute(
            """UPDATE companies SET
               company_name=?, note=?,
               applied_2023=?, applied_2024=?, applied_2025=?,
               applied_2026=?, applied_2027=?, industry=?
               WHERE id=?""",
            (
                data.get("company_name", ""),
                data.get("note", ""),
                1 if data.get("applied_2023") else 0,
                1 if data.get("applied_2024") else 0,
                1 if data.get("applied_2025") else 0,
                1 if data.get("applied_2026") else 0,
                1 if data.get("applied_2027") else 0,
                industry_tags,
                company_id,
            ),
        )
    conn.commit()
    conn.close()


def delete_company(company_id: int, user_id: int | None = None):
    conn = get_connection()
    if user_id is not None:
        conn.execute("DELETE FROM companies WHERE id=? AND user_id=?", (company_id, user_id))
    else:
        conn.execute("DELETE FROM companies WHERE id=?", (company_id,))
    conn.commit()
    conn.close()


def bulk_delete_companies(ids: list, user_id: int | None = None) -> int:
    """Delete multiple companies by ID. Returns number of rows deleted."""
    if not ids:
        return 0
    safe_ids = []
    for raw in ids:
        try:
            n = int(raw)
            if n > 0:
                safe_ids.append(n)
        except (TypeError, ValueError):
            pass
    if not safe_ids:
        return 0
    placeholders = ",".join("?" for _ in safe_ids)
    conn = get_connection()
    if user_id is not None:
        conn.execute(
            f"DELETE FROM companies WHERE id IN ({placeholders}) AND user_id=?",
            (*safe_ids, user_id),
        )
    else:
        conn.execute(f"DELETE FROM companies WHERE id IN ({placeholders})", safe_ids)
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def get_industry_tag_suggestions(
    user_id: int | None = None,
    pool_enabled: bool = True,
    limit: int = 120,
) -> list[str]:
    """Return unique industry tags visible to the current user."""
    tags: list[str] = []
    seen: set[str] = set()
    for company in get_companies(user_id=user_id, pool_enabled=pool_enabled):
        for raw in (company.get("industry") or "").split(","):
            tag = raw.strip()
            key = tag.lower()
            if not tag or key in seen:
                continue
            seen.add(key)
            tags.append(tag)
            if len(tags) >= limit:
                return tags
    return tags


def _auto_add_or_update_company(
    company_name: str,
    industry: str | None = None,
    user_id: int | None = None,
    *,
    date_applied: str | None = None,
    status: str | None = None,
    app_id: int | None = None,
):
    """Create/update company and keep industry tags + applied-year flags in sync."""
    if not company_name:
        return
    normalized_industry = _normalize_industry_tags(industry)
    applied_col = None
    if date_applied and _should_track_company_year(status):
        year = (date_applied or "")[:4]
        if year.isdigit():
            applied_col = f"applied_{year}"

    conn = get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()}
    can_mark_applied = bool(applied_col and applied_col in cols and applied_col in _APPLIED_YEAR_COLUMNS)
    if user_id is not None:
        row = conn.execute(
            "SELECT id, industry FROM companies WHERE LOWER(company_name)=? AND user_id=?",
            (company_name.lower(), user_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, industry FROM companies WHERE LOWER(company_name)=? AND user_id IS NULL",
            (company_name.lower(),),
        ).fetchone()

    company_added = False
    if row is None:
        if can_mark_applied:
            insert_sql_by_year = {
                "applied_2023": "INSERT INTO companies (company_name, industry, applied_2023) VALUES (?,?,1)",
                "applied_2024": "INSERT INTO companies (company_name, industry, applied_2024) VALUES (?,?,1)",
                "applied_2025": "INSERT INTO companies (company_name, industry, applied_2025) VALUES (?,?,1)",
                "applied_2026": "INSERT INTO companies (company_name, industry, applied_2026) VALUES (?,?,1)",
                "applied_2027": "INSERT INTO companies (company_name, industry, applied_2027) VALUES (?,?,1)",
            }
            conn.execute(insert_sql_by_year[applied_col], (company_name, normalized_industry))
            if user_id is not None:
                conn.execute(
                    "UPDATE companies SET user_id=? WHERE id=last_insert_rowid()",
                    (user_id,),
                )
        else:
            conn.execute(
                "INSERT INTO companies (company_name, industry, user_id) VALUES (?,?,?)",
                (company_name, normalized_industry, user_id),
            )
        company_added = True
    else:
        merged = _merge_industry_tags(row["industry"], normalized_industry)
        if can_mark_applied:
            update_sql_by_year = {
                "applied_2023": "UPDATE companies SET industry=?, applied_2023=1 WHERE id=?",
                "applied_2024": "UPDATE companies SET industry=?, applied_2024=1 WHERE id=?",
                "applied_2025": "UPDATE companies SET industry=?, applied_2025=1 WHERE id=?",
                "applied_2026": "UPDATE companies SET industry=?, applied_2026=1 WHERE id=?",
                "applied_2027": "UPDATE companies SET industry=?, applied_2027=1 WHERE id=?",
            }
            conn.execute(update_sql_by_year[applied_col], (merged, row["id"]))
        else:
            conn.execute(
                "UPDATE companies SET industry=? WHERE id=?",
                (merged, row["id"]),
            )
    conn.commit()
    conn.close()

    if company_added and not normalized_industry and app_id is not None:
        from .reminders import create_reminder

        msg = (
            f"Company '{company_name}' was added without industry tags. "
            "Open Company Tracker to complete its industry/tags."
        )
        create_reminder(app_id, msg)

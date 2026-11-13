"""Company CRUD helpers."""

import contextvars
import re
from datetime import date

from .connection import get_connection

# During a bulk import, new companies without industry tags are collected here
# (one summary reminder at the end) instead of one inbox reminder each.
_untagged_during_import: contextvars.ContextVar = contextvars.ContextVar(
    "untagged_during_import", default=None)


_NON_COMPANY_TRACKING_STATUSES = {
    "Job_Expired",
    "Drafting_CV",
    "Select_Status",
    "Not_Applying",
}
_APPLIED_COLUMN = re.compile(r"^applied_(\d{4})$")
_FIRST_YEAR, _LAST_YEAR = 1990, 2100


def applied_year_columns(conn) -> list[str]:
    """The companies table's applied_YYYY columns, oldest year first."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
    return sorted(c for c in cols if _APPLIED_COLUMN.match(c))


def ensure_applied_year_column(conn, year) -> str | None:
    """Make sure an applied_YYYY column exists for *year* (one per year, added as
    years come up, instead of a fixed 2023-2027 set).  Returns its name, or None
    for a year outside 1990-2100."""
    try:
        year = int(year)
    except (TypeError, ValueError):
        return None
    if not _FIRST_YEAR <= year <= _LAST_YEAR:
        return None
    col = f"applied_{year}"               # safe: built from a validated integer
    if col not in applied_year_columns(conn):
        conn.execute(f"ALTER TABLE companies ADD COLUMN {col} INTEGER DEFAULT 0")
    return col


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
            if owner is not None and owner != user_id:
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
    ensure_applied_year_column(conn, date.today().year)   # the form always offers this year
    years = applied_year_columns(conn)
    columns = ["company_name", "note", *years, "user_id", "industry"]
    values = [data.get("company_name", ""), data.get("note", ""),
              *[1 if data.get(col) else 0 for col in years], user_id, industry_tags]
    conn.execute(
        f"INSERT INTO companies ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        values,
    )
    conn.commit()
    conn.close()


def update_company(company_id: int, data):
    industry_tags = _normalize_industry_tags(data.get("industry", ""))
    conn = get_connection()
    ensure_applied_year_column(conn, date.today().year)   # the form always offers this year
    years = applied_year_columns(conn)
    assignments = ", ".join(f"{col}=?" for col in ["company_name", "note", *years, "industry"])
    conn.execute(
        f"UPDATE companies SET {assignments} WHERE id=?",
        [data.get("company_name", ""), data.get("note", ""),
         *[1 if data.get(col) else 0 for col in years], industry_tags, company_id],
    )
    conn.commit()
    conn.close()


def delete_company(company_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM companies WHERE id=?", (company_id,))
    conn.commit()
    conn.close()


def bulk_delete_companies(ids: list) -> int:
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
    conn.execute(f"DELETE FROM companies WHERE id IN ({placeholders})", safe_ids)
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def _auto_add_or_update_company(
    company_name: str,
    industry: str | None = None,
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
    if applied_col:
        applied_col = ensure_applied_year_column(conn, applied_col[len("applied_"):])
    can_mark_applied = bool(applied_col)
    row = conn.execute(
        "SELECT id, industry FROM companies WHERE LOWER(company_name)=?",
        (company_name.lower(),),
    ).fetchone()

    company_added = False
    if row is None:
        if can_mark_applied:
            conn.execute(
                f"INSERT INTO companies (company_name, industry, {applied_col}) VALUES (?,?,1)",
                (company_name, normalized_industry),
            )
        else:
            conn.execute(
                "INSERT INTO companies (company_name, industry) VALUES (?,?)",
                (company_name, normalized_industry),
            )
        company_added = True
    else:
        merged = _merge_industry_tags(row["industry"], normalized_industry)
        if can_mark_applied:
            conn.execute(
                f"UPDATE companies SET industry=?, {applied_col}=1 WHERE id=?",
                (merged, row["id"]),
            )
        else:
            conn.execute(
                "UPDATE companies SET industry=? WHERE id=?",
                (merged, row["id"]),
            )
    conn.commit()
    conn.close()

    if company_added and not normalized_industry and app_id is not None:
        collected = _untagged_during_import.get()
        if collected is not None:
            collected.append((company_name, app_id))
            return
        from .reminders import create_reminder

        msg = (
            f"Company '{company_name}' was added without industry tags. "
            "Open Company Tracker to complete its industry/tags."
        )
        create_reminder(app_id, msg)

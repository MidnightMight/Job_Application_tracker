"""Company CRUD helpers."""

from .connection import get_connection


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
            data.get("industry", "") or None,
        ),
    )
    conn.commit()
    conn.close()


def update_company(company_id: int, data):
    conn = get_connection()
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
            data.get("industry", "") or None,
            company_id,
        ),
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


def _auto_add_or_update_company(company_name: str, industry: str | None = None):
    """Create a company record if it doesn't exist; update industry if missing."""
    if not company_name:
        return
    conn = get_connection()
    row = conn.execute(
        "SELECT id, industry FROM companies WHERE LOWER(company_name)=?",
        (company_name.lower(),),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO companies (company_name, industry) VALUES (?,?)",
            (company_name, industry or None),
        )
    elif industry and not row["industry"]:
        conn.execute(
            "UPDATE companies SET industry=? WHERE id=?",
            (industry, row["id"]),
        )
    conn.commit()
    conn.close()

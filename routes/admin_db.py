"""Admin-only database viewer and editor.

Provides:
  GET  /admin/db                — table list with row counts
  GET  /admin/db/<table>        — paginated row viewer
  GET  /admin/db/<table>/<pk>   — edit form for a single row
  POST /admin/db/<table>/<pk>   — save edits to a single row
  POST /admin/db/query          — run a read-only SELECT query

All routes require admin access (login_required + is_admin).
Sensitive columns (password_hash, api_key) are masked in the viewer.
"""

import sqlite3

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for,
)

from db.connection import get_connection, DB_PATH
from .auth import admin_required

bp = Blueprint("admin_db", __name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pre-built mapping from external name → trusted literal table name.
# Using a dict lookup breaks any taint chain — the value used in SQL is always
# a string literal defined here in source, never the user-supplied value.
_TABLE_MAP: dict[str, str] = {
    "applications":   "applications",
    "companies":      "companies",
    "status_history": "status_history",
    "statuses":       "statuses",
    "reminders":      "reminders",
    "settings":       "settings",
    "users":          "users",
    "user_ai_settings": "user_ai_settings",
}

# Columns whose values are masked in the viewer / editor (display only).
_SENSITIVE_COLUMNS = {"password_hash", "api_key"}

_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_table(name: str) -> str | None:
    """Return the trusted table name literal for *name*, or None if unknown."""
    return _TABLE_MAP.get(name)


def _get_tables() -> list[dict]:
    """Return table metadata (name, row_count) for all viewable tables."""
    conn = get_connection()
    results = []
    for safe_name in sorted(_TABLE_MAP.values()):
        # safe_name is a literal from _TABLE_MAP — not user input.
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM " + safe_name  # nosec B608
            ).fetchone()[0]
        except sqlite3.OperationalError:
            count = 0
        results.append({"name": safe_name, "row_count": count})
    conn.close()
    return results


def _get_columns(safe_name: str) -> list[str]:
    """Return ordered column names for *safe_name* (must be a trusted literal)."""
    conn = get_connection()
    cols = [row[1] for row in conn.execute(
        "PRAGMA table_info(" + safe_name + ")"  # nosec B608
    ).fetchall()]
    conn.close()
    return cols


def _mask_row(row: dict) -> dict:
    """Replace sensitive column values with a placeholder string."""
    return {
        k: ("••••••••" if k in _SENSITIVE_COLUMNS and v else v)
        for k, v in row.items()
    }


def _get_any_pk_column(safe_name: str) -> tuple[str | None, bool]:
    """Return (pk_column_name, is_integer_type) for *safe_name*.

    The `settings` table uses a TEXT primary key ('key'); most others use INTEGER.
    Returns (None, False) when there is no single primary key column.
    *safe_name* must already be a trusted literal from _TABLE_MAP.
    """
    conn = get_connection()
    rows = conn.execute(
        "PRAGMA table_info(" + safe_name + ")"  # nosec B608
    ).fetchall()
    conn.close()
    for row in rows:
        if row[5] == 1:  # pk flag
            col_type = (row[2] or "").upper()
            is_int = "INT" in col_type
            return row[1], is_int
    return None, False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/admin/db")
@admin_required
def db_overview():
    """Show all tables with row counts."""
    tables = _get_tables()
    return render_template("admin_db.html", view="overview", tables=tables,
                           db_path=DB_PATH)


@bp.route("/admin/db/<table>")
@admin_required
def db_table(table: str):
    """Show paginated rows for *table*."""
    safe_name = _safe_table(table)
    if not safe_name:
        flash(f"Table '{table}' is not accessible.", "danger")
        return redirect(url_for("admin_db.db_overview"))

    page = max(1, request.args.get("page", 1, type=int))
    offset = (page - 1) * _PAGE_SIZE

    conn = get_connection()
    try:
        # safe_name is a literal from _TABLE_MAP, not user input.
        total = conn.execute(
            "SELECT COUNT(*) FROM " + safe_name  # nosec B608
        ).fetchone()[0]
        rows_raw = conn.execute(
            "SELECT * FROM " + safe_name + " LIMIT ? OFFSET ?",  # nosec B608
            (_PAGE_SIZE, offset),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        conn.close()
        flash(f"Could not read table: {exc}", "danger")
        return redirect(url_for("admin_db.db_overview"))
    conn.close()

    columns = _get_columns(safe_name)
    rows = [_mask_row(dict(r)) for r in rows_raw]
    pk_col, pk_is_int = _get_any_pk_column(safe_name)
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)

    return render_template(
        "admin_db.html",
        view="table",
        table=safe_name,
        columns=columns,
        rows=rows,
        pk_col=pk_col,
        pk_is_int=pk_is_int,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route("/admin/db/<table>/<int:pk>", methods=["GET", "POST"])
@admin_required
def db_row(table: str, pk: int):
    """View or edit a single row identified by its integer primary key."""
    return _db_row_impl(table, pk)


@bp.route("/admin/db/<table>/edit/<path:pk>", methods=["GET", "POST"])
@admin_required
def db_row_text(table: str, pk: str):
    """View or edit a single row identified by a text primary key (e.g. settings.key)."""
    return _db_row_impl(table, pk)


def _db_row_impl(table: str, pk):
    """Shared implementation for integer and text PK row editing."""
    safe_name = _safe_table(table)
    if not safe_name:
        flash(f"Table '{table}' is not accessible.", "danger")
        return redirect(url_for("admin_db.db_overview"))

    pk_col, pk_is_int = _get_any_pk_column(safe_name)
    if not pk_col:
        flash(f"Table '{safe_name}' has no editable primary key.", "warning")
        return redirect(url_for("admin_db.db_table", table=safe_name))

    # pk_col comes from PRAGMA table_info (DB schema), not user input.
    conn = get_connection()
    row_raw = conn.execute(
        "SELECT * FROM " + safe_name + " WHERE " + pk_col + "=?",  # nosec B608
        (pk,),
    ).fetchone()

    if row_raw is None:
        conn.close()
        flash("Row not found.", "danger")
        return redirect(url_for("admin_db.db_table", table=safe_name))

    if request.method == "POST":
        # Columns come from DB schema (PRAGMA), not user input.
        columns = _get_columns(safe_name)
        updates = {}
        for col in columns:
            if col == pk_col:
                continue
            if col in _SENSITIVE_COLUMNS:
                new_val = request.form.get(col, "")
                if new_val and new_val != "••••••••":
                    updates[col] = new_val
            else:
                updates[col] = request.form.get(col, "")

        if updates:
            # All keys in `updates` are columns fetched from PRAGMA (DB schema).
            set_clause = ", ".join(c + "=?" for c in updates)
            values = list(updates.values()) + [pk]
            try:
                conn.execute(
                    "UPDATE " + safe_name + " SET " + set_clause  # nosec B608
                    + " WHERE " + pk_col + "=?",
                    values,
                )
                conn.commit()
                flash("Row updated successfully.", "success")
            except sqlite3.Error as exc:
                conn.rollback()
                flash(f"Update failed: {exc}", "danger")
        else:
            flash("No changes to save.", "info")

        conn.close()
        if pk_is_int:
            return redirect(url_for("admin_db.db_row", table=safe_name, pk=pk))
        return redirect(url_for("admin_db.db_row_text", table=safe_name, pk=pk))

    conn.close()
    row = dict(row_raw)
    columns = _get_columns(safe_name)
    return render_template(
        "admin_db.html",
        view="row",
        table=safe_name,
        pk=pk,
        pk_col=pk_col,
        pk_is_int=pk_is_int,
        row=row,
        columns=columns,
        sensitive=_SENSITIVE_COLUMNS,
    )


@bp.route("/admin/db/query", methods=["GET", "POST"])
@admin_required
def db_query():
    """Read-only SQL query console (SELECT only)."""
    results = None
    columns = []
    error = None
    sql = ""

    if request.method == "POST":
        sql = request.form.get("sql", "").strip()
        # Only allow SELECT/PRAGMA — WAL mode + query_only PRAGMA reinforce this.
        normalised = sql.upper().lstrip()
        if not normalised.startswith("SELECT") and not normalised.startswith("PRAGMA"):
            error = "Only SELECT and PRAGMA statements are permitted."
        else:
            conn = get_connection()
            try:
                conn.execute("PRAGMA query_only=ON")
                cur = conn.execute(sql)
                rows_raw = cur.fetchmany(500)
                columns = [d[0] for d in cur.description] if cur.description else []
                results = [dict(zip(columns, r)) for r in rows_raw]
                for row in results:
                    for k in list(row.keys()):
                        if k in _SENSITIVE_COLUMNS:
                            row[k] = "••••••••"
            except sqlite3.Error as exc:
                error = str(exc)
            finally:
                conn.close()

    return render_template(
        "admin_db.html",
        view="query",
        sql=sql,
        results=results,
        columns=columns,
        error=error,
    )

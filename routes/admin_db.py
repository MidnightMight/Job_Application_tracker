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
import re as _re

from flask import (
    Blueprint, flash, redirect, render_template,
    request, url_for, jsonify,
)

import db
from db.connection import get_connection, DB_PATH
from .auth import admin_required

bp = Blueprint("admin_db", __name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Only allow viewing/editing these tables.
_VIEWABLE_TABLES = {
    "applications", "companies", "status_history",
    "statuses", "reminders", "settings", "users", "user_ai_settings",
}

# Columns whose values are masked in the viewer / editor (display only).
_SENSITIVE_COLUMNS = {"password_hash", "api_key"}

_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_tables() -> list[dict]:
    """Return table metadata (name, row_count) for all viewable tables."""
    conn = get_connection()
    results = []
    for table in sorted(_VIEWABLE_TABLES):
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        except sqlite3.OperationalError:
            count = 0
        results.append({"name": table, "row_count": count})
    conn.close()
    return results


def _get_columns(table: str) -> list[str]:
    """Return ordered column names for *table*."""
    conn = get_connection()
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


def _mask_row(row: dict) -> dict:
    """Replace sensitive column values with a placeholder string."""
    return {
        k: ("••••••••" if k in _SENSITIVE_COLUMNS and v else v)
        for k, v in row.items()
    }


def _get_pk_column(table: str) -> str | None:
    """Return the name of the INTEGER PRIMARY KEY column for *table*, or None."""
    conn = get_connection()
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    conn.close()
    for row in rows:
        # cid, name, type, notnull, dflt_value, pk
        if row[5] == 1 and "INT" in (row[2] or "").upper():
            return row[1]
    return None


def _get_any_pk_column(table: str) -> tuple[str | None, bool]:
    """Return (pk_column_name, is_integer_type).

    The `settings` table uses a TEXT primary key ('key'), most others use INTEGER.
    Returns (None, False) when there is no single primary key column.
    """
    conn = get_connection()
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
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
    if table not in _VIEWABLE_TABLES:
        flash(f"Table '{table}' is not accessible.", "danger")
        return redirect(url_for("admin_db.db_overview"))

    page = max(1, request.args.get("page", 1, type=int))
    offset = (page - 1) * _PAGE_SIZE

    conn = get_connection()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        rows_raw = conn.execute(
            f"SELECT * FROM {table} LIMIT ? OFFSET ?",  # noqa: S608
            (_PAGE_SIZE, offset),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        conn.close()
        flash(f"Could not read table: {exc}", "danger")
        return redirect(url_for("admin_db.db_overview"))
    conn.close()

    columns = _get_columns(table)
    rows = [_mask_row(dict(r)) for r in rows_raw]
    pk_col, pk_is_int = _get_any_pk_column(table)
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)

    return render_template(
        "admin_db.html",
        view="table",
        table=table,
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
    if table not in _VIEWABLE_TABLES:
        flash(f"Table '{table}' is not accessible.", "danger")
        return redirect(url_for("admin_db.db_overview"))

    pk_col, pk_is_int = _get_any_pk_column(table)
    if not pk_col:
        flash(f"Table '{table}' has no editable primary key.", "warning")
        return redirect(url_for("admin_db.db_table", table=table))

    conn = get_connection()
    row_raw = conn.execute(
        f"SELECT * FROM {table} WHERE {pk_col}=?",  # noqa: S608
        (pk,),
    ).fetchone()

    if row_raw is None:
        conn.close()
        flash("Row not found.", "danger")
        return redirect(url_for("admin_db.db_table", table=table))

    if request.method == "POST":
        columns = _get_columns(table)
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
            set_clause = ", ".join(f"{c}=?" for c in updates)
            values = list(updates.values()) + [pk]
            try:
                conn.execute(
                    f"UPDATE {table} SET {set_clause} WHERE {pk_col}=?",  # noqa: S608
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
            return redirect(url_for("admin_db.db_row", table=table, pk=pk))
        return redirect(url_for("admin_db.db_row_text", table=table, pk=pk))

    conn.close()
    row = dict(row_raw)
    columns = _get_columns(table)
    return render_template(
        "admin_db.html",
        view="row",
        table=table,
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
        # Only allow SELECT statements (very basic guard; WAL mode prevents writes anyway).
        normalised = sql.upper().lstrip()
        if not normalised.startswith("SELECT") and not normalised.startswith("PRAGMA"):
            error = "Only SELECT and PRAGMA statements are permitted."
        else:
            conn = get_connection()
            conn.execute("PRAGMA query_only=ON")
            try:
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

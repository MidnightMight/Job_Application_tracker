"""Database connection and low-level helpers."""

import sqlite3
import os
from datetime import date

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobs.db"),
)

# Ensure the data directory exists when using the default local path.
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Static fallback year list — prefer get_dynamic_years() in views.
YEARS = [2023, 2024, 2025, 2026, 2027]

_ALLOWED_TABLES = {
    "applications", "companies", "status_history",
    "statuses", "reminders", "settings", "users", "user_ai_settings",
    "attention_snoozes",
}
_ALLOWED_COLUMNS = {
    "contact", "additional_notes", "status_changed_at", "last_contact_date",
    "ai_fit_score", "ai_fit_verdict", "ai_matching_skills", "ai_skill_gaps",
    "ai_recommendation", "last_modified_at", "job_expiry_date", "industry",
    "bg_color", "text_color", "user_id", "needs_password_setup", "use_admin_ai",
    "last_login_at", "archived", "archived_at", "reminder_type",
    "snooze_until",
}
_ALLOWED_DEFINITIONS = {"TEXT", "INTEGER DEFAULT 0", "INTEGER", "REAL", "TEXT DEFAULT ''"}

# Fields that may be updated via the bulk-action route.
_BULK_UPDATE_FIELDS = {
    "status", "cover_letter", "resume", "date_applied", "last_contact_date",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _add_column_if_missing(c, table: str, column: str, definition: str):
    """Safely add a column to an existing table (migration helper).

    All three parameters are validated against allowlists so that this
    internal helper can never be used as a SQL-injection vector.
    """
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"_add_column_if_missing: unknown table '{table}'")
    if column not in _ALLOWED_COLUMNS:
        raise ValueError(f"_add_column_if_missing: unknown column '{column}'")
    if definition not in _ALLOWED_DEFINITIONS:
        raise ValueError(f"_add_column_if_missing: unknown definition '{definition}'")
    existing = [row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in existing:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def get_dynamic_years(user_id=None) -> list[int]:
    """Return a sorted list of years to display in navigation.

    Includes every year that has at least one application plus the current
    calendar year.  Falls back to the static YEARS list if the DB is empty.
    When user_id is given, only that user's applications are considered.
    """
    current = date.today().year
    try:
        conn = get_connection()
        sql = (
            "SELECT DISTINCT CAST(strftime('%Y', date_applied) AS INTEGER) AS yr "
            "FROM applications WHERE date_applied IS NOT NULL AND date_applied != ''"
        )
        params: list = []
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        sql += " ORDER BY yr"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        years_from_db = [r["yr"] for r in rows if r["yr"]]
    except Exception:
        years_from_db = []

    year_set = set(years_from_db) | {current}
    return sorted(year_set)

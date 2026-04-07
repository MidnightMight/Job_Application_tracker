"""Reminders / inbox helpers."""

from datetime import datetime

from .connection import get_connection
from .init_db import PENDING_STATUSES


def get_pending_for_reminders(days_threshold: int) -> list:
    """Return pending applications that have been waiting more than days_threshold days
    and don't already have an undismissed reminder created within the last day."""
    conn = get_connection()
    placeholders = ",".join("?" for _ in PENDING_STATUSES)
    rows = conn.execute(
        f"""SELECT a.* FROM applications a
            WHERE a.status IN ({placeholders})
              AND julianday('now') - julianday(a.date_applied) > ?
              AND NOT EXISTS (
                  SELECT 1 FROM reminders r
                  WHERE r.application_id = a.id
                    AND r.dismissed = 0
                    AND julianday('now') - julianday(r.created_at) < 1
              )
        """,
        (*PENDING_STATUSES, days_threshold),
    ).fetchall()
    conn.close()
    from .applications import _enrich
    return [_enrich(dict(r)) for r in rows]


def create_reminder(application_id: int, message: str):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "INSERT INTO reminders (application_id, message, created_at, dismissed) VALUES (?,?,?,0)",
        (application_id, message, now),
    )
    conn.commit()
    conn.close()


def get_reminders(unread_only: bool = False) -> list:
    conn = get_connection()
    sql = (
        "SELECT r.*, a.company, a.job_desc, a.status, a.date_applied "
        "FROM reminders r "
        "LEFT JOIN applications a ON a.id = r.application_id "
    )
    if unread_only:
        sql += "WHERE r.dismissed=0 "
    sql += "ORDER BY r.created_at DESC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_reminder(reminder_id: int):
    conn = get_connection()
    conn.execute("UPDATE reminders SET dismissed=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def dismiss_all_reminders():
    conn = get_connection()
    conn.execute("UPDATE reminders SET dismissed=1")
    conn.commit()
    conn.close()


def get_unread_reminder_count() -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE dismissed=0"
    ).fetchone()[0]
    conn.close()
    return count

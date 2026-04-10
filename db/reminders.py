"""Reminders / inbox helpers."""

from datetime import datetime

from .connection import get_connection
from .init_db import PENDING_STATUSES


def get_pending_for_reminders(days_threshold: int, user_id=None) -> list:
    """Return pending applications that have been waiting more than days_threshold days
    and don't already have an undismissed reminder created within the last day."""
    conn = get_connection()
    placeholders = ",".join("?" for _ in PENDING_STATUSES)
    sql = f"""SELECT a.* FROM applications a
            WHERE a.status IN ({placeholders})
              AND julianday('now') - julianday(a.date_applied) > ?
              AND NOT EXISTS (
                  SELECT 1 FROM reminders r
                  WHERE r.application_id = a.id
                    AND r.dismissed = 0
                    AND julianday('now') - julianday(r.created_at) < 1
              )
        """
    params: list = [*PENDING_STATUSES, days_threshold]
    if user_id is not None:
        sql += " AND a.user_id = ?"
        params.append(user_id)
    rows = conn.execute(sql, params).fetchall()
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


def get_reminders(unread_only: bool = False, user_id=None) -> list:
    conn = get_connection()
    sql = (
        "SELECT r.*, a.company, a.job_desc, a.status, a.date_applied "
        "FROM reminders r "
        "LEFT JOIN applications a ON a.id = r.application_id "
    )
    conditions = []
    params: list = []
    if unread_only:
        conditions.append("r.dismissed=0")
    if user_id is not None:
        conditions.append("(a.user_id = ? OR a.user_id IS NULL)")
        params.append(user_id)
    if conditions:
        sql += "WHERE " + " AND ".join(conditions) + " "
    sql += "ORDER BY r.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_reminder(reminder_id: int):
    conn = get_connection()
    conn.execute("UPDATE reminders SET dismissed=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def dismiss_all_reminders(user_id=None):
    conn = get_connection()
    if user_id is not None:
        conn.execute(
            "UPDATE reminders SET dismissed=1 WHERE id IN ("
            "  SELECT r.id FROM reminders r "
            "  LEFT JOIN applications a ON a.id = r.application_id "
            "  WHERE a.user_id = ? OR a.user_id IS NULL"
            ")",
            (user_id,),
        )
    else:
        conn.execute("UPDATE reminders SET dismissed=1")
    conn.commit()
    conn.close()


def get_unread_reminder_count(user_id=None) -> int:
    conn = get_connection()
    if user_id is not None:
        count = conn.execute(
            "SELECT COUNT(*) FROM reminders r "
            "LEFT JOIN applications a ON a.id = r.application_id "
            "WHERE r.dismissed=0 AND (a.user_id = ? OR a.user_id IS NULL)",
            (user_id,),
        ).fetchone()[0]
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM reminders WHERE dismissed=0"
        ).fetchone()[0]
    conn.close()
    return count

"""Reminders / inbox helpers."""

import logging
from datetime import datetime

from .connection import get_connection

logger = logging.getLogger(__name__)


def create_reminder(application_id: int, message: str, reminder_type: str = ""):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "INSERT INTO reminders (application_id, message, created_at, dismissed, reminder_type)"
        " VALUES (?,?,?,0,?)",
        (application_id, message, now, reminder_type or None),
    )
    conn.commit()
    conn.close()


def _statuses_in_stages(ranks, user_id=None) -> list:
    """Statuses (visible to *user_id*) whose stage, from status_rank(), is in *ranks*."""
    from .applications import status_rank
    from .statuses import get_status_options
    return [s for s in get_status_options(user_id=user_id) if status_rank(s) in ranks]


def get_stalled_submitted_applications(threshold_days: int, user_id=None) -> list:
    """Applications that went to the employer and are stale by the same rule as the
    stale badge (applied: *threshold_days*; interview, assessment, offer: a week;
    never while a next step is scheduled), without a stall_checkin reminder in the
    last 7 days."""
    from .applications import _STALE_ACTIVE_RANKS, _STALE_APPLIED_RANKS, _enrich
    statuses = _statuses_in_stages(_STALE_ACTIVE_RANKS + _STALE_APPLIED_RANKS, user_id=user_id)
    if not statuses:
        return []
    placeholders = ",".join("?" for _ in statuses)
    sql = f"""
        SELECT a.* FROM applications a
        WHERE a.status IN ({placeholders})
          AND COALESCE(a.archived, 0) = 0
          AND NOT EXISTS (
              SELECT 1 FROM reminders r
              WHERE r.application_id = a.id
                AND r.dismissed = 0
                AND r.reminder_type = 'stall_checkin'
                AND julianday('now') - julianday(r.created_at) < 7
          )
    """
    params: list = [*statuses]
    if user_id is not None:
        sql += " AND a.user_id = ?"
        params.append(user_id)
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    apps = [_enrich(dict(r), threshold_days) for r in rows]
    return [a for a in apps if a["is_stale"]]


def get_likely_rejected_applications(threshold_days: int, user_id=None) -> list:
    """Return applications still waiting on the employer with no status change for longer than
    *threshold_days*, that don't already have a recent likely_rejected reminder.

    Only ``status_changed_at`` is used here — contact alone does not prevent an
    application from being flagged as likely rejected.
    """
    # Went to the employer and still open: applied, awaiting, assessment, interview.
    statuses = _statuses_in_stages((1, 2, 5, 6), user_id=user_id)
    if not statuses:
        return []

    placeholders = ",".join("?" for _ in statuses)
    sql = f"""
        SELECT a.* FROM applications a
        WHERE a.status IN ({placeholders})
          AND COALESCE(a.archived, 0) = 0
          AND julianday('now') - julianday(
                COALESCE(a.status_changed_at, a.date_applied)
              ) > ?
          AND NOT EXISTS (
              SELECT 1 FROM reminders r
              WHERE r.application_id = a.id
                AND r.dismissed = 0
                AND r.reminder_type = 'likely_rejected'
                AND julianday('now') - julianday(r.created_at) < 7
          )
          -- A next step still to come (e.g. an interview date) means it isn't dead yet.
          AND (julianday(a.next_action_date) IS NULL
               OR date(a.next_action_date) < date('now', 'localtime'))
    """
    params: list = [*statuses, threshold_days]
    if user_id is not None:
        sql += " AND a.user_id = ?"
        params.append(user_id)
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    from .applications import _enrich
    return [_enrich(dict(r)) for r in rows]


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


def get_due_next_steps_without_reminder(user_id=None) -> list:
    """Applications whose next step is due today or overdue and has no reminder yet.

    A reminder counts when it was made on or after the due date, so moving the
    date later gives a fresh reminder when the new date arrives.
    """
    conn = get_connection()
    sql = """SELECT a.* FROM applications a
            WHERE COALESCE(a.archived, 0) = 0
              AND COALESCE(a.next_action_date, '') != ''
              AND a.next_action_date <= date('now', 'localtime')
              AND NOT EXISTS (
                  SELECT 1 FROM reminders r
                  WHERE r.application_id = a.id
                    AND r.reminder_type = 'next_step'
                    AND substr(r.created_at, 1, 10) >= a.next_action_date
              )"""
    params: list = []
    if user_id is not None:
        sql += " AND a.user_id = ?"
        params.append(user_id)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

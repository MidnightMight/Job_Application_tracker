"""Reminders / inbox helpers."""

import logging
from datetime import datetime

from .connection import get_connection
from .init_db import PENDING_STATUSES

logger = logging.getLogger(__name__)


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


def _get_submitted_range_statuses(user_id=None) -> list:
    """Return the ordered statuses between Submitted and Rejected (exclusive of Rejected)."""
    try:
        from .statuses import get_status_options
        ordered = get_status_options(user_id=user_id)
        submitted_idx = ordered.index("Submitted")
        rejected_idx = ordered.index("Rejected")
        start = min(submitted_idx, rejected_idx)
        end = max(submitted_idx, rejected_idx)
        # Submitted inclusive, Rejected exclusive — the "active waiting" range.
        return ordered[start:end]
    except (ValueError, ImportError):
        logger.debug("_get_submitted_range_statuses: falling back to defaults")
        return [
            "Submitted", "Online_Assessment", "Awaiting_Response",
            "Interview_Scheduled", "Interview_In_Person",
        ]
    except Exception:
        logger.exception("_get_submitted_range_statuses: unexpected error")
        return []


def get_stalled_submitted_applications(threshold_days: int, user_id=None) -> list:
    """Return submitted-range applications with no status change AND no recorded contact
    for longer than *threshold_days*, that don't already have a recent stall_checkin reminder.

    Both ``status_changed_at`` and ``last_contact_date`` are considered — whichever is
    more recent resets the stall clock.
    """
    statuses = _get_submitted_range_statuses(user_id=user_id)
    if not statuses:
        return []

    placeholders = ",".join("?" for _ in statuses)
    # Use julianday() for all date arithmetic to avoid string-comparison edge cases.
    # When both status_changed_at and last_contact_date are NULL the inner expression
    # falls back to date_applied; if that is also NULL the row evaluates to NULL > ?
    # which is FALSE in SQLite — the application is silently excluded (correct behaviour).
    sql = f"""
        SELECT a.* FROM applications a
        WHERE a.status IN ({placeholders})
          AND COALESCE(a.archived, 0) = 0
          AND julianday('now') - julianday(
                CASE
                  WHEN julianday(a.last_contact_date) IS NOT NULL
                   AND julianday(a.last_contact_date) >= julianday(COALESCE(a.status_changed_at, a.date_applied))
                  THEN a.last_contact_date
                  ELSE COALESCE(a.status_changed_at, a.date_applied)
                END
              ) > ?
          AND NOT EXISTS (
              SELECT 1 FROM reminders r
              WHERE r.application_id = a.id
                AND r.dismissed = 0
                AND r.reminder_type = 'stall_checkin'
                AND julianday('now') - julianday(r.created_at) < 7
          )
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


def get_likely_rejected_applications(threshold_days: int, user_id=None) -> list:
    """Return submitted-range applications with no status change for longer than
    *threshold_days*, that don't already have a recent likely_rejected reminder.

    Only ``status_changed_at`` is used here — contact alone does not prevent an
    application from being flagged as likely rejected.
    """
    statuses = _get_submitted_range_statuses(user_id=user_id)
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

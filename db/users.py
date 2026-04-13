"""User management helpers."""

import sqlite3
from datetime import datetime

from .connection import get_connection


def get_users() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_users() -> int:
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n


def add_user(username: str, password_hash: str, is_admin: bool = False,
             needs_password_setup: bool = False) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Username cannot be empty."
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at, needs_password_setup)"
            " VALUES (?,?,?,?,?)",
            (username, password_hash, 1 if is_admin else 0, now, 1 if needs_password_setup else 0),
        )
        conn.commit()
        return True, f"User '{username}' added."
    except sqlite3.IntegrityError:
        return False, f"Username '{username}' already exists."
    finally:
        conn.close()


def delete_user(user_id: int) -> tuple[bool, str]:
    conn = get_connection()
    row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    username = row["username"]
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return True, f"User '{username}' deleted."


def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, is_admin, needs_password_setup"
        " FROM users WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_user_password(user_id: int, password_hash: str) -> None:
    """Store a new password for *user_id* and clear the needs_password_setup flag."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash=?, needs_password_setup=0 WHERE id=?",
        (password_hash, user_id),
    )
    conn.commit()
    conn.close()


def reassign_null_user_data(user_id: int) -> int:
    """Assign all applications that have no owner (user_id IS NULL) to user_id.

    Called when login is first enabled so that records created in single-user
    mode (before any login was required) remain visible to the first admin user
    rather than disappearing because queries now filter by user_id.

    Returns the number of application rows updated.
    """
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE applications SET user_id=? WHERE user_id IS NULL",
        (user_id,),
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

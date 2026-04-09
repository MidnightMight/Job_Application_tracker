"""Status management helpers."""

import sqlite3

from .connection import get_connection

# Statuses that must never be deleted — they are core workflow states.
PROTECTED_STATUSES = frozenset({
    "Select_Status",
    "Drafting_Application",
    "Submitted",
    "Rejected",
    "Offer_Received",
    "Offer_Rejected",
    "Not_Applying",
    "Job_Expired",
})


def get_status_options() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT name FROM statuses ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def add_status(name: str) -> tuple[bool, str]:
    name = name.strip().replace(" ", "_")
    if not name:
        return False, "Status name cannot be empty."
    conn = get_connection()
    try:
        max_order = conn.execute("SELECT MAX(sort_order) FROM statuses").fetchone()[0] or 0
        conn.execute(
            "INSERT INTO statuses (name, sort_order) VALUES (?,?)",
            (name, max_order + 1),
        )
        conn.commit()
        return True, f"Status '{name}' added."
    except sqlite3.IntegrityError:
        return False, f"Status '{name}' already exists."
    finally:
        conn.close()


def move_status(name: str, direction: str) -> tuple[bool, str]:
    """Move a status up or down in sort order. direction must be 'up' or 'down'."""
    if direction not in ("up", "down"):
        return False, "Invalid direction."
    conn = get_connection()
    rows = conn.execute("SELECT id, name, sort_order FROM statuses ORDER BY sort_order, id").fetchall()
    names = [r["name"] for r in rows]
    if name not in names:
        conn.close()
        return False, f"Status '{name}' not found."
    idx = names.index(name)
    if direction == "up" and idx == 0:
        conn.close()
        return False, "Already at the top."
    if direction == "down" and idx == len(names) - 1:
        conn.close()
        return False, "Already at the bottom."
    swap_idx = idx - 1 if direction == "up" else idx + 1
    # Swap sort_order values between the two rows
    a = rows[idx]
    b = rows[swap_idx]
    conn.execute("UPDATE statuses SET sort_order=? WHERE id=?", (b["sort_order"], a["id"]))
    conn.execute("UPDATE statuses SET sort_order=? WHERE id=?", (a["sort_order"], b["id"]))
    conn.commit()
    conn.close()
    return True, f"Status '{name}' moved {direction}."


def delete_status(name: str) -> tuple[bool, str]:
    """Delete a custom status. Prevents deletion of protected statuses or those in use."""
    if name in PROTECTED_STATUSES:
        return False, f"'{name}' is a protected status and cannot be deleted."
    conn = get_connection()
    in_use = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status=?", (name,)
    ).fetchone()[0]
    if in_use:
        conn.close()
        return False, f"Cannot delete '{name}' — {in_use} application(s) use it."
    conn.execute("DELETE FROM statuses WHERE name=?", (name,))
    conn.commit()
    conn.close()
    return True, f"Status '{name}' deleted."

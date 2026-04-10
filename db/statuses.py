"""Status management helpers."""

import re
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

_HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _valid_color(value: str) -> str:
    """Return the colour string if it is a valid CSS hex colour, else ''."""
    stripped = value.strip()
    return stripped if _HEX_COLOR_RE.match(stripped) else ""


def _accessible_condition(user_id=None) -> tuple[str, list]:
    """Return a SQL WHERE fragment and params that restricts to statuses
    visible to *user_id*.

    When login is disabled (user_id=None) every status is visible.
    When login is enabled (user_id=<int>) only global statuses (user_id IS NULL)
    and the user's own statuses (user_id = ?) are visible.
    """
    if user_id is None:
        return "1=1", []
    return "(user_id IS NULL OR user_id = ?)", [user_id]


def get_status_options(user_id=None) -> list[str]:
    """Return ordered status names visible to user_id (global + own)."""
    cond, params = _accessible_condition(user_id)
    conn = get_connection()
    rows = conn.execute(
        f"SELECT name FROM statuses WHERE {cond} ORDER BY sort_order, id",
        params,
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def get_status_rows(user_id=None) -> list[dict]:
    """Return full status rows (id, name, sort_order, bg_color, text_color, user_id)
    visible to user_id."""
    cond, params = _accessible_condition(user_id)
    conn = get_connection()
    rows = conn.execute(
        f"SELECT id, name, sort_order, bg_color, text_color, user_id "
        f"FROM statuses WHERE {cond} ORDER BY sort_order, id",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_status_styles(user_id=None) -> dict[str, dict]:
    """Return a dict {name: {bg_color, text_color}} for statuses that have
    custom colours set and are visible to user_id.
    Per-user colours override global ones when names collide."""
    cond, params = _accessible_condition(user_id)
    conn = get_connection()
    # Fetch global first, then user-specific so user rows can override
    rows = conn.execute(
        f"SELECT name, bg_color, text_color, user_id "
        f"FROM statuses WHERE {cond} ORDER BY (user_id IS NULL) ASC",
        params,
    ).fetchall()
    conn.close()
    result = {}
    for r in rows:
        bg = (r["bg_color"] or "").strip()
        tc = (r["text_color"] or "").strip()
        if bg or tc:
            result[r["name"]] = {"bg_color": bg, "text_color": tc}
    return result


def add_status(name: str, bg_color: str = "", text_color: str = "", user_id=None) -> tuple[bool, str]:
    """Add a new status.  When user_id is given, the status is private to that user."""
    name = name.strip().replace(" ", "_")
    if not name:
        return False, "Status name cannot be empty."
    bg = _valid_color(bg_color)
    text = _valid_color(text_color)
    conn = get_connection()
    try:
        max_order = conn.execute("SELECT MAX(sort_order) FROM statuses").fetchone()[0] or 0
        conn.execute(
            "INSERT INTO statuses (name, sort_order, bg_color, text_color, user_id) "
            "VALUES (?,?,?,?,?)",
            (name, max_order + 1, bg or None, text or None, user_id),
        )
        conn.commit()
        return True, f"Status '{name}' added."
    except sqlite3.IntegrityError:
        return False, f"Status '{name}' already exists."
    finally:
        conn.close()


def move_status(name: str, direction: str, user_id=None) -> tuple[bool, str]:
    """Move a status up or down in the order visible to user_id."""
    if direction not in ("up", "down"):
        return False, "Invalid direction."
    cond, params = _accessible_condition(user_id)
    conn = get_connection()
    rows = conn.execute(
        f"SELECT id, name, sort_order FROM statuses WHERE {cond} ORDER BY sort_order, id",
        params,
    ).fetchall()
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
    a = rows[idx]
    b = rows[swap_idx]
    conn.execute("UPDATE statuses SET sort_order=? WHERE id=?", (b["sort_order"], a["id"]))
    conn.execute("UPDATE statuses SET sort_order=? WHERE id=?", (a["sort_order"], b["id"]))
    conn.commit()
    conn.close()
    return True, f"Status '{name}' moved {direction}."


def delete_status(name: str, user_id=None) -> tuple[bool, str]:
    """Delete a custom status.

    Rules:
    - Protected statuses can never be deleted.
    - A global status (user_id IS NULL) can only be deleted when no user_id is
      given (i.e. admin / single-user mode).
    - A per-user status can only be deleted by its owner.
    - A status cannot be deleted while any application uses it (scoped to the
      requesting user when user_id is given).
    """
    if name in PROTECTED_STATUSES:
        return False, f"'{name}' is a protected status and cannot be deleted."
    conn = get_connection()
    row = conn.execute(
        "SELECT id, user_id FROM statuses WHERE name=? AND (user_id IS NULL OR user_id=?)",
        (name, user_id if user_id is not None else -1),
    ).fetchone()
    if row is None:
        # Check if it exists at all — better error message
        exists = conn.execute("SELECT 1 FROM statuses WHERE name=?", (name,)).fetchone()
        conn.close()
        if exists:
            return False, "You do not have permission to delete this status."
        return False, f"Status '{name}' not found."

    # For global statuses, only allow deletion when called without a user_id (admin/single-user).
    if row["user_id"] is None and user_id is not None:
        conn.close()
        return False, "Only admins can delete global statuses."

    # Check in-use (scoped to the requesting user's applications when applicable)
    if user_id is not None:
        in_use = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status=? AND user_id=?",
            (name, user_id),
        ).fetchone()[0]
    else:
        in_use = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status=?", (name,)
        ).fetchone()[0]

    if in_use:
        conn.close()
        return False, f"Cannot delete '{name}' — {in_use} application(s) use it."

    if user_id is not None:
        conn.execute("DELETE FROM statuses WHERE name=? AND user_id=?", (name, user_id))
    else:
        conn.execute("DELETE FROM statuses WHERE name=? AND user_id IS NULL", (name,))
    conn.commit()
    conn.close()
    return True, f"Status '{name}' deleted."


def update_status_colors(name: str, bg_color: str, text_color: str, user_id=None) -> tuple[bool, str]:
    """Set or clear the custom bg/text colours for a status accessible to user_id."""
    bg = _valid_color(bg_color)
    text = _valid_color(text_color)
    cond, params = _accessible_condition(user_id)
    conn = get_connection()
    row = conn.execute(
        f"SELECT id, user_id FROM statuses WHERE name=? AND {cond}",
        [name, *params],
    ).fetchone()
    if not row:
        conn.close()
        return False, f"Status '{name}' not found."
    # Only allow editing global statuses in admin/single-user mode
    if row["user_id"] is None and user_id is not None:
        # Instead of editing in place, create a user-specific override
        existing_override = conn.execute(
            "SELECT id FROM statuses WHERE name=? AND user_id=?", (name, user_id)
        ).fetchone()
        if existing_override:
            conn.execute(
                "UPDATE statuses SET bg_color=?, text_color=? WHERE name=? AND user_id=?",
                (bg or None, text or None, name, user_id),
            )
        else:
            # Copy the global status as a user-specific one with colours
            max_order = conn.execute("SELECT MAX(sort_order) FROM statuses").fetchone()[0] or 0
            conn.execute(
                "INSERT INTO statuses (name, sort_order, bg_color, text_color, user_id) "
                "VALUES (?,?,?,?,?)",
                (name, max_order + 1, bg or None, text or None, user_id),
            )
    else:
        conn.execute(
            "UPDATE statuses SET bg_color=?, text_color=? WHERE name=? AND "
            + ("user_id=?" if user_id is not None else "user_id IS NULL"),
            [bg or None, text or None, name] + ([user_id] if user_id is not None else []),
        )
    conn.commit()
    conn.close()
    return True, f"Colours for '{name}' updated."


def reorder_statuses(names: list[str], user_id=None) -> tuple[bool, str]:
    """Set the sort_order of accessible statuses to match the given list order."""
    if not names:
        return False, "No names provided."
    cond, params = _accessible_condition(user_id)
    conn = get_connection()
    existing = {
        r["name"]
        for r in conn.execute(
            f"SELECT name FROM statuses WHERE {cond}", params
        ).fetchall()
    }
    for i, name in enumerate(names):
        if name not in existing:
            conn.close()
            return False, f"Unknown status '{name}'."
        # Only update the specific row accessible to this user
        if user_id is not None:
            # Prefer the user's own row; fall back to global
            own_row = conn.execute(
                "SELECT id FROM statuses WHERE name=? AND user_id=?", (name, user_id)
            ).fetchone()
            if own_row:
                conn.execute("UPDATE statuses SET sort_order=? WHERE id=?", (i, own_row["id"]))
            else:
                conn.execute(
                    "UPDATE statuses SET sort_order=? WHERE name=? AND user_id IS NULL",
                    (i, name),
                )
        else:
            conn.execute(
                "UPDATE statuses SET sort_order=? WHERE name=? AND user_id IS NULL",
                (i, name),
            )
    conn.commit()
    conn.close()
    return True, "Order saved."

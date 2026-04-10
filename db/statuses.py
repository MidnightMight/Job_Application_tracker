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


def get_status_options() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT name FROM statuses ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def get_status_styles() -> dict[str, dict]:
    """Return a dict {name: {bg_color, text_color}} for statuses that have
    custom colours set.  Only entries with at least one non-empty colour are
    included."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, bg_color, text_color FROM statuses"
    ).fetchall()
    conn.close()
    result = {}
    for r in rows:
        bg = (r["bg_color"] or "").strip()
        tc = (r["text_color"] or "").strip()
        if bg or tc:
            result[r["name"]] = {"bg_color": bg, "text_color": tc}
    return result


def add_status(name: str, bg_color: str = "", text_color: str = "") -> tuple[bool, str]:
    name = name.strip().replace(" ", "_")
    if not name:
        return False, "Status name cannot be empty."
    bg = _valid_color(bg_color)
    text = _valid_color(text_color)
    conn = get_connection()
    try:
        max_order = conn.execute("SELECT MAX(sort_order) FROM statuses").fetchone()[0] or 0
        conn.execute(
            "INSERT INTO statuses (name, sort_order, bg_color, text_color) VALUES (?,?,?,?)",
            (name, max_order + 1, bg or None, text or None),
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


def update_status_colors(name: str, bg_color: str, text_color: str) -> tuple[bool, str]:
    """Set or clear the custom bg/text colours for a status."""
    bg = _valid_color(bg_color)
    text = _valid_color(text_color)
    conn = get_connection()
    row = conn.execute("SELECT id FROM statuses WHERE name=?", (name,)).fetchone()
    if not row:
        conn.close()
        return False, f"Status '{name}' not found."
    conn.execute(
        "UPDATE statuses SET bg_color=?, text_color=? WHERE name=?",
        (bg or None, text or None, name),
    )
    conn.commit()
    conn.close()
    return True, f"Colours for '{name}' updated."


def reorder_statuses(names: list[str]) -> tuple[bool, str]:
    """Set the sort_order of statuses to match the given list order."""
    if not names:
        return False, "No names provided."
    conn = get_connection()
    existing = {r["name"] for r in conn.execute("SELECT name FROM statuses").fetchall()}
    for i, name in enumerate(names):
        if name not in existing:
            conn.close()
            return False, f"Unknown status '{name}'."
        conn.execute("UPDATE statuses SET sort_order=? WHERE name=?", (i, name))
    conn.commit()
    conn.close()
    return True, "Order saved."

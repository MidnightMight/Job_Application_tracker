"""Settings helpers."""

from .connection import get_connection


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def get_all_settings() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ── Years in the Applications menu ──────────────────────────────────────────
# Stored as the years someone *hid* (per user; one set with login off), so a new
# year shows up on its own.

def _hidden_years_key(user_id) -> str:
    return "hidden_years" if user_id is None else f"hidden_years_{user_id}"


def get_hidden_years(user_id=None) -> set[int]:
    raw = get_setting(_hidden_years_key(user_id), "")
    return {int(y) for y in raw.split(",") if y.strip().isdigit()}


def set_hidden_years(user_id, years) -> None:
    set_setting(_hidden_years_key(user_id), ",".join(str(int(y)) for y in sorted(set(years))))


def get_menu_years(user_id=None) -> list[int]:
    """The years to list in the Applications menu: every year with applications
    plus the current one, minus the ones hidden in Settings (never none)."""
    from datetime import date
    from .connection import get_dynamic_years
    every = get_dynamic_years(user_id=user_id)
    hidden = get_hidden_years(user_id)
    return [y for y in every if y not in hidden] or [date.today().year]


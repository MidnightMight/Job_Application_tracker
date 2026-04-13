"""Per-user AI settings (provider, API key, model, and profile)."""

from .connection import get_connection

_VALID_PROVIDERS = {"ollama", "openai", "anthropic", "custom"}

_ALLOWED_FIELDS = {
    "ai_provider", "api_key", "api_url", "ai_model",
    "profile_skills", "profile_experience", "profile_summary",
}

_DEFAULTS: dict = {
    "ai_provider":        "ollama",
    "api_key":            "",
    "api_url":            "",
    "ai_model":           "",
    "profile_skills":     "",
    "profile_experience": "",
    "profile_summary":    "",
}


def get_user_ai_settings(user_id: int | None) -> dict:
    """Return a dict of AI settings for *user_id*, filled with defaults."""
    if user_id is None:
        return dict(_DEFAULTS)
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_ai_settings WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        merged = dict(_DEFAULTS)
        merged.update({k: (row[k] or "") for k in _DEFAULTS})
        return merged
    return dict(_DEFAULTS)


def save_user_ai_settings(user_id: int, fields: dict) -> None:
    """Upsert AI settings for *user_id*.  Only keys in _ALLOWED_FIELDS are written."""
    safe = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not safe:
        return
    conn = get_connection()
    # Ensure a row exists first.
    conn.execute(
        "INSERT OR IGNORE INTO user_ai_settings (user_id) VALUES (?)", (user_id,)
    )
    for key, value in safe.items():
        # key is validated against the allowlist above, so safe to use in SQL.
        conn.execute(
            f"UPDATE user_ai_settings SET {key}=? WHERE user_id=?",  # noqa: S608
            (str(value), user_id),
        )
    conn.commit()
    conn.close()


def user_has_own_ai(user_id: int | None) -> bool:
    """Return True when the user has configured a non-Ollama AI provider with an API key."""
    if user_id is None:
        return False
    cfg = get_user_ai_settings(user_id)
    return cfg["ai_provider"] != "ollama" and bool(cfg["api_key"].strip())

"""Per-user AI settings (provider, API key, model, and profile)."""

from .connection import get_connection

_VALID_PROVIDERS = {"ollama", "openai", "anthropic", "custom"}

_ALLOWED_FIELDS = {
    "ai_provider", "api_key", "api_url", "ai_model",
    "profile_skills", "profile_experience", "profile_summary",
    "use_admin_ai",
}

# Pre-built parameterised UPDATE statements — avoids any f-string SQL construction.
_COL_UPDATES: dict[str, str] = {
    "ai_provider":        "UPDATE user_ai_settings SET ai_provider=?        WHERE user_id=?",
    "api_key":            "UPDATE user_ai_settings SET api_key=?            WHERE user_id=?",
    "api_url":            "UPDATE user_ai_settings SET api_url=?            WHERE user_id=?",
    "ai_model":           "UPDATE user_ai_settings SET ai_model=?           WHERE user_id=?",
    "profile_skills":     "UPDATE user_ai_settings SET profile_skills=?     WHERE user_id=?",
    "profile_experience": "UPDATE user_ai_settings SET profile_experience=? WHERE user_id=?",
    "profile_summary":    "UPDATE user_ai_settings SET profile_summary=?    WHERE user_id=?",
    "use_admin_ai":       "UPDATE user_ai_settings SET use_admin_ai=?       WHERE user_id=?",
}

_DEFAULTS: dict = {
    "ai_provider":        "ollama",
    "api_key":            "",
    "api_url":            "",
    "ai_model":           "",
    "profile_skills":     "",
    "profile_experience": "",
    "profile_summary":    "",
    "use_admin_ai":       1,
}


# With login off there is no user (user_id None).  The one person using the app
# keeps the same AI settings in the settings table under these keys; when login is
# switched on they move to the first admin (adopt_single_user_ai_settings).
_SINGLE_PREFIX = "single_user_ai_"


def _single_user_settings() -> dict:
    from .settings import get_setting
    merged = dict(_DEFAULTS)
    for k in _DEFAULTS:
        value = get_setting(_SINGLE_PREFIX + k, "")
        if value != "":
            merged[k] = int(value) if k == "use_admin_ai" else value
    return merged


def adopt_single_user_ai_settings(user_id: int) -> None:
    """Give the login-off AI settings to *user_id* when they have none of their own."""
    from .settings import get_setting
    conn = get_connection()
    has_own = conn.execute("SELECT 1 FROM user_ai_settings WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    stored = {k: get_setting(_SINGLE_PREFIX + k, "") for k in _ALLOWED_FIELDS}
    if not has_own and any(v != "" for v in stored.values()):
        save_user_ai_settings(user_id, {k: v for k, v in stored.items() if v != ""})


def get_user_ai_settings(user_id: int | None) -> dict:
    """Return a dict of AI settings for *user_id* (None = login off), filled with defaults."""
    if user_id is None:
        return _single_user_settings()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_ai_settings WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        merged = dict(_DEFAULTS)
        for k in _DEFAULTS:
            if k == "use_admin_ai":
                # Preserve integer type; default to 1 when column is NULL.
                val = row[k] if row[k] is not None else 1
                merged[k] = int(val)
            else:
                merged[k] = row[k] or ""
        return merged
    return dict(_DEFAULTS)


def save_user_ai_settings(user_id: int, fields: dict) -> None:
    """Upsert AI settings for *user_id*.  Only keys in _ALLOWED_FIELDS are written."""
    safe = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not safe:
        return
    if user_id is None:
        from .settings import set_setting
        for key, value in safe.items():
            set_setting(_SINGLE_PREFIX + key, str(value))
        return
    conn = get_connection()
    # Ensure a row exists first.
    conn.execute(
        "INSERT OR IGNORE INTO user_ai_settings (user_id) VALUES (?)", (user_id,)
    )
    for key, value in safe.items():
        conn.execute(_COL_UPDATES[key], (str(value), user_id))
    conn.commit()
    conn.close()


def user_has_own_ai(user_id: int | None) -> bool:
    """Return True when the user has opted out of the admin server and has a valid provider.

    Conditions:
    - ``use_admin_ai`` is 0 (user explicitly chose their own provider), AND
    - a provider is configured with required credentials/URL.
    """
    cfg = get_user_ai_settings(user_id)
    if int(cfg.get("use_admin_ai", 1)):
        return False
    provider = cfg.get("ai_provider", "ollama")
    if provider == "ollama":
        return bool(cfg.get("api_url", "").strip())
    if provider == "custom":
        return bool(cfg.get("api_url", "").strip())
    return bool(cfg.get("api_key", "").strip())

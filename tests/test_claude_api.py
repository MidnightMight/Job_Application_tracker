"""Claude (Anthropic) calls, with the HTTP layer replaced by canned replies."""

import io
import json
import urllib.error

import pytest

from routes import api


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _reply(monkeypatch, body=None, http_error=None):
    sent = {}

    def fake_urlopen(req, timeout=0):
        sent["url"], sent["body"] = req.full_url, json.loads(req.data or b"{}")
        if http_error:
            code, err = http_error
            raise urllib.error.HTTPError(req.full_url, code, "err", {},
                                         io.BytesIO(json.dumps({"error": {"message": err}}).encode()))
        return _Resp(json.dumps(body).encode())
    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_reads_the_text_after_a_thinking_block(monkeypatch):
    sent = _reply(monkeypatch, {"stop_reason": "end_turn", "content": [
        {"type": "thinking", "thinking": ""},
        {"type": "text", "text": '{"company": "Acme"}'},
    ]})
    assert api._call_anthropic("ad", "key", "") == '{"company": "Acme"}'
    assert sent["body"]["model"] == "claude-opus-5-5"          # current default
    assert sent["body"]["max_tokens"] >= 16000                  # room for thinking + answer


def test_refusal_and_errors_read_plainly(monkeypatch):
    _reply(monkeypatch, {"stop_reason": "refusal", "content": []})
    with pytest.raises(RuntimeError, match="declined"):
        api._call_anthropic("ad", "key", "claude-opus-5-5")

    _reply(monkeypatch, http_error=(404, "model: claude-3-haiku-20240307"))
    with pytest.raises(RuntimeError, match="isn't available.*claude-opus-5-5"):
        api._call_anthropic("ad", "key", "claude-3-haiku-20240307")

    _reply(monkeypatch, http_error=(401, "invalid x-api-key"))
    with pytest.raises(RuntimeError, match="rejected"):
        api._call_anthropic("ad", "bad", "")

    _reply(monkeypatch, http_error=(400, "Your credit balance is too low"))
    with pytest.raises(RuntimeError, match="out of credit"):
        api._call_anthropic("ad", "key", "")


def test_settings_page_has_the_claude_guide(client, monkeypatch):
    import db
    from werkzeug.security import generate_password_hash
    import app as app_module
    monkeypatch.setattr(app_module, "DEPLOYMENT_MODE", "docker")  # AI section is hidden in local mode
    db.set_setting("login_enabled", "1")      # the per-user AI card needs login on
    try:
        if not db.get_user_by_username("guide"):
            db.add_user("guide", generate_password_hash("pw"), is_admin=True)
        user = db.get_user_by_username("guide")
        with client.session_transaction() as sess:
            sess["user_id"], sess["username"], sess["is_admin"] = user["id"], "guide", True
        page = client.get("/settings?section=ai").get_data(as_text=True)
    finally:
        db.set_setting("login_enabled", "0")
    assert 'id="claudeGuide"' in page and "platform.claude.com" in page
    assert "claude-3-haiku" not in page


def test_claude_works_with_login_off_and_moves_to_the_admin_later(client, monkeypatch):
    import db
    from werkzeug.security import generate_password_hash
    # Login off: the AI card is there and saving works.
    page = client.get("/settings?section=ai").get_data(as_text=True)
    assert 'id="claudeGuide"' in page and 'name="ai_provider"' in page
    client.post("/settings?section=ai", data={"action": "save_user_ai", "use_admin_ai": "0",
                                               "ai_provider": "anthropic", "api_key": "sk-ant-test"})
    assert db.user_has_own_ai(None)
    assert db.get_user_ai_settings(None)["ai_provider"] == "anthropic"
    sent = _reply(monkeypatch, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]})
    assert api._call_ai("hello", None) == "ok" and sent["url"].endswith("/v1/messages")
    # Switching login on later hands the settings to the first admin.
    db.add_user("boss", generate_password_hash("pw"), is_admin=True)
    boss = db.get_user_by_username("boss")
    db.adopt_single_user_ai_settings(boss["id"])
    assert db.get_user_ai_settings(boss["id"])["api_key"] == "sk-ant-test"


def test_local_mode_keeps_your_own_provider(client, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "DEPLOYMENT_MODE", "local")
    page = client.get("/settings?section=ai").get_data(as_text=True)
    assert "Shared Ollama server not available in local mode" in page
    assert 'name="ai_provider"' in page and 'id="claudeGuide"' in page

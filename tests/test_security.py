"""CSRF protection, the generated secret key and the /healthz endpoint."""

import glob
import os
import re

import db
import app as app_module

_TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _token(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


# ── CSRF ─────────────────────────────────────────────────────────────────────

def test_every_post_form_has_a_csrf_token():
    missing = []
    for path in glob.glob(os.path.join(_TEMPLATES, "*.html")):
        html = open(path, encoding="utf-8").read()
        for m in re.finditer(r"<form\b[^>]*>(.*?)</form>", html, re.S | re.I):
            tag = m.group(0)[:m.group(0).index(">") + 1]
            if re.search(r'method\s*=\s*["\']?post', tag, re.I) and "csrf_token()" not in m.group(1):
                missing.append(f"{os.path.basename(path)}: {tag[:60]}")
    assert not missing, missing


def test_post_without_token_is_rejected(csrf_client):
    response = csrf_client.post("/application/add", data={"company": "Acme", "job_desc": "Engineer"})
    assert response.status_code == 302          # back to the form with a message
    assert db.get_applications(include_archived=True) == []


def test_post_with_token_from_the_page_works(csrf_client):
    token = _token(csrf_client.get("/application/add").get_data(as_text=True))
    response = csrf_client.post("/application/add", data={
        "csrf_token": token, "company": "Acme", "job_desc": "Engineer",
    })
    assert response.status_code == 302
    assert [a["company"] for a in db.get_applications(include_archived=True)] == ["Acme"]


def test_json_post_needs_the_header(csrf_client):
    html = csrf_client.get("/settings?section=statuses").get_data(as_text=True)
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)

    rejected = csrf_client.post("/settings/reorder-statuses", json={"names": []})
    assert rejected.status_code == 400
    assert rejected.get_json()["ok"] is False

    accepted = csrf_client.post("/settings/reorder-statuses", json={"names": []},
                                headers={"X-CSRFToken": token})
    assert accepted.status_code == 200


def test_rejected_form_redirects_back_to_referring_page(csrf_client):
    response = csrf_client.post("/application/add", data={"company": "Acme"},
                                headers={"Referer": "http://localhost/application/add"})
    assert response.headers["Location"].endswith("/application/add")


# ── Secret key ───────────────────────────────────────────────────────────────

def test_secret_key_from_environment_wins(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("SECRET_KEY", "from-env")
    assert app_module._load_secret_key() == "from-env"
    assert not (tmp_path / "secret_key").exists()


def test_secret_key_is_generated_once_and_kept(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    first = app_module._load_secret_key()
    assert len(first) == 64
    assert (tmp_path / "secret_key").read_text() == first
    assert os.stat(tmp_path / "secret_key").st_mode & 0o777 == 0o600
    assert app_module._load_secret_key() == first


def test_empty_secret_key_file_is_replaced(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    (tmp_path / "secret_key").write_text("")
    key = app_module._load_secret_key()
    assert key and (tmp_path / "secret_key").read_text() == key


# ── Health check ─────────────────────────────────────────────────────────────

def test_healthz_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_healthz_skips_onboarding_and_login(client):
    db.set_setting("onboarding_complete", "0")
    db.set_setting("login_enabled", "1")
    assert client.get("/healthz").status_code == 200


def test_healthz_reports_database_errors(client, monkeypatch):
    def broken():
        raise OSError("disk gone")
    monkeypatch.setattr(db, "get_connection", broken)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.get_json() == {"status": "error"}

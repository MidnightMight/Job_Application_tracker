"""Tests for update_check: version comparison, caching and the navbar badge."""

import db
import update_check


def test_v_prefix_in_either_case_is_understood():
    assert update_check.is_newer("V1.3.0", "1.2.4")
    assert update_check.is_newer("v1.3.0", "1.2.4")


def test_lettered_tag_is_newer_than_plain():
    assert update_check.is_newer("V1.2.4A", "1.2.4")
    assert update_check.is_newer("V1.2.4B", "1.2.4A")
    assert not update_check.is_newer("V1.2.4A", "1.3.0")


def test_equal_and_older_versions_are_not_newer():
    assert not update_check.is_newer("v1.3.0", "1.3.0")
    assert not update_check.is_newer("1.2", "1.2.0")
    assert not update_check.is_newer("v1.2.2", "1.3.0")


def test_unreadable_tags_are_never_newer():
    assert not update_check.is_newer("latest", "1.3.0")
    assert not update_check.is_newer("", "1.3.0")


def test_cached_info_drives_navbar_badge(client):
    update_check.store_latest_release("V9.9.9", "https://example.com/release")
    html = client.get("/").get_data(as_text=True)
    assert 'id="updateAvailableBadge"' in html
    assert "Update v9.9.9" in html

    update_check.store_latest_release("v1.0.0", "https://example.com/old")
    html = client.get("/").get_data(as_text=True)
    assert 'id="updateAvailableBadge"' not in html


def test_check_update_route_uses_lenient_comparison(client, monkeypatch):
    monkeypatch.setattr(update_check, "fetch_latest_release",
                        lambda repo, timeout=8: {"tag": "V9.0.0A", "url": "https://example.com/r"})
    data = client.get("/settings/check-update").get_json()
    assert data["ok"] and data["update_available"]
    assert data["latest"] == "9.0.0A"
    assert db.get_setting("latest_release_tag") == "V9.0.0A"


def test_refresh_respects_disable_setting(monkeypatch):
    calls = []
    monkeypatch.setattr(update_check, "fetch_latest_release",
                        lambda repo, timeout=8: calls.append(repo) or {"tag": "v1", "url": ""})
    db.set_setting("update_check_enabled", "0")
    try:
        assert update_check.refresh_latest_release("x/y") is None
        assert calls == []
    finally:
        db.set_setting("update_check_enabled", "1")


def test_refresh_swallows_network_errors(monkeypatch):
    def boom(repo, timeout=8):
        raise OSError("no network")
    monkeypatch.setattr(update_check, "fetch_latest_release", boom)
    assert update_check.refresh_latest_release("x/y") is None

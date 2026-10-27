"""Midnight Lite restyle: logo, status names, dashboard honeycomb, year view."""

import re
from datetime import date

import db
from app import _status_label


def _add(company, status, day="03-01"):
    return db.add_application({"company": company, "job_desc": "Engineer", "status": status,
                               "date_applied": f"{date.today().year}-{day}"})


def test_status_label():
    assert _status_label("Select_Status") == "No status"
    assert _status_label("") == "No status"
    assert _status_label(None) == "No status"
    assert _status_label("Offer_Received") == "Offer Received"


def test_logo_and_icons_are_served(client):
    for path in ("/static/icons/logo.svg", "/static/icons/icon.svg", "/static/icons/favicon-32.png",
                 "/static/icons/apple-touch-icon.png", "/static/icons/icon-192.png"):
        response = client.get(path)
        assert response.status_code == 200, path
        response.close()
    html = client.get("/").get_data(as_text=True)
    assert "icons/logo.svg" in html
    assert 'rel="icon"' in html


def test_dashboard_honeycomb_follows_status_order(client):
    _add("Acme", "Rejected")
    _add("Beta", "Submitted")
    _add("Gamma", "Submitted")
    html = client.get("/").get_data(as_text=True)
    cells = re.findall(r'<span class="ml-cell-label">([^<]+)</span>', html)
    order = db.get_status_options()
    expected = [s.replace("_", " ") for s in order if s in ("Submitted", "Rejected")]
    assert cells == expected
    assert '<span class="ml-cell-count">2</span>' in html
    assert f"/year/{date.today().year}?status=Submitted" in html


def test_dashboard_without_applications_shows_empty_state(client):
    html = client.get("/").get_data(as_text=True)
    assert "No applications yet this year." in html
    assert 'class="ml-cell"' not in html


def test_dashboard_charts_live_in_a_script_file(client):
    html = client.get("/").get_data(as_text=True)
    assert "js/dashboard.js" in html
    assert "new Chart(" not in html


def test_status_placeholder_never_shown_raw(client):
    _add("Acme", "Select_Status")
    for path in ("/", f"/year/{date.today().year}", "/search?q=acme"):
        html = client.get(path).get_data(as_text=True)
        visible = re.sub(r'(class|value|href|name)="[^"]*"', "", html)
        assert "Select_Status" not in visible and "Select Status" not in visible, path


def test_year_view_bulk_bar_starts_hidden(client):
    _add("Acme", "Submitted")
    html = client.get(f"/year/{date.today().year}").get_data(as_text=True)
    assert re.search(r'class="ml-bulkbar[^"]*\bd-none\b[^"]*" id="bulkToolbar"', html)
    assert 'id="filterForm"' in html


def test_menu_holds_import_export_settings_and_logout(client):
    db.set_setting("login_enabled", "1")
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "admin"
    html = client.get("/").get_data(as_text=True)
    menu = html[html.index('class="dropdown-menu dropdown-menu-end ml-menu'):]
    menu = menu[:menu.index("</ul>")]
    for text in ("Import CSV", "Export", "Settings", "themeToggleBtn", "Log out"):
        assert text in menu, text

"""Smoke tests: every main page renders, and the import flow works end to end."""

import io
import re

import pytest

import db


@pytest.mark.parametrize("path", [
    "/", "/year/2026", "/search?q=acme", "/application/add", "/companies",
    "/inbox", "/export", "/application/import",
    "/settings", "/settings?section=statuses", "/settings?section=ai",
    "/settings?section=updates", "/report/workforce",
])
def test_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200, path


def test_edit_page_uses_external_scripts(client):
    db.bulk_import_applications([{"company": "Acme", "job_desc": "Engineer"}])
    app_id = db.get_applications(include_archived=True)[0]["id"]
    html = client.get(f"/application/edit/{app_id}").get_data(as_text=True)
    assert "js/application_form.js" in html
    assert "window.APP_FORM_CONFIG" in html


def test_static_scripts_are_served(client):
    for name in ("application_form.js", "application_ai_fill.js", "application_ai_fit.js",
                 "settings.js", "settings_statuses.js", "workforce_report.js"):
        response = client.get(f"/static/js/{name}")
        assert response.status_code == 200, name
        assert "{{" not in response.get_data(as_text=True), name


def test_import_flow_with_update_existing(client):
    db.bulk_import_applications([{"company": "Acme", "job_desc": "Engineer",
                                  "date_applied": "2026-10-01"}])
    app_id = db.get_applications(include_archived=True)[0]["id"]
    csv_text = (
        "id,company,job_desc,date_applied,status\n"
        f"{app_id},Acme,Engineer,2026-10-01,Submitted\n"
        ",Beta,Hardware Engineer,,Drafting_Application\n"
    )
    upload = client.post("/application/import", data={
        "csv_file": (io.BytesIO(csv_text.encode()), "apps.csv"),
        "header_row": "1",
    }, content_type="multipart/form-data")
    page = upload.get_data(as_text=True)
    assert 'name="update_existing"' in page
    # Pick up the hidden csv_content exactly as the browser would post it.
    import html as _html
    csv_content = _html.unescape(re.search(r'name="csv_content" value="([^"]*)"', page).group(1))
    result = client.post("/application/import", data={
        "stage": "import",
        "csv_content": csv_content,
        "col_map_0": "id", "col_map_1": "company", "col_map_2": "job_desc",
        "col_map_3": "date_applied", "col_map_4": "status",
        "update_existing": "1",
    })
    body = result.get_data(as_text=True)
    assert result.status_code == 200
    assert "Rows Updated" in body
    statuses = {a["company"]: a["status"] for a in db.get_applications(include_archived=True)}
    assert statuses == {"Acme": "Submitted", "Beta": "Drafting_Application"}

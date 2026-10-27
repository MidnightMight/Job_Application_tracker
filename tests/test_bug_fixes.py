"""Regression tests for bugs found while adding CSRF protection."""

import re
from datetime import date

import db


def test_search_with_undated_application(client):
    db.add_application({"company": "Acme", "job_desc": "Engineer", "date_applied": ""})
    response = client.get("/search?q=acme")
    assert response.status_code == 200
    assert b"Acme" in response.data


def test_year_view_has_no_nested_forms(client):
    year = date.today().year
    app_id = db.add_application({"company": "Acme", "job_desc": "Engineer",
                                 "date_applied": f"{year}-03-01", "status": "Rejected"})
    html = client.get(f"/year/{year}").get_data(as_text=True)
    depth = 0
    for tag in re.findall(r"<(/?)form\b", html):
        depth += -1 if tag else 1
        assert depth <= 1, "a <form> is nested inside another form"
    assert f'formaction="/application/delete/{app_id}"' in html
    assert f'formaction="/application/archive/{app_id}"' in html


def test_row_delete_from_year_view(client):
    year = date.today().year
    app_id = db.add_application({"company": "Acme", "job_desc": "Engineer",
                                 "date_applied": f"{year}-03-01"})
    # What the browser sends: every bulkForm field, posted to the button's formaction.
    client.post(f"/application/delete/{app_id}", data={"bulk_status": "", "bulk_action": ""})
    assert db.get_application(app_id) is None


def test_service_worker_may_control_the_whole_site(client):
    response = client.get("/static/sw.js")
    assert response.headers.get("Service-Worker-Allowed") == "/"
    response.close()


def test_logout_needs_post(client):
    assert client.get("/logout").status_code == 405
    response = client.post("/logout")
    assert response.status_code == 302


def test_logout_post_needs_csrf_token(csrf_client):
    with csrf_client.session_transaction() as sess:
        sess["user_id"] = 1
    csrf_client.post("/logout", data={"x": "1"})
    with csrf_client.session_transaction() as sess:
        assert sess.get("user_id") == 1


def test_missing_page_is_404_not_500(client):
    assert client.get("/no-such-page").status_code == 404
    assert client.get("/application/999999").status_code in (302, 404)

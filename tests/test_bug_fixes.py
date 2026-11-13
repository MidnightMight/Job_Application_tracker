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


def test_sample_data_does_not_come_back_after_deleting_everything():
    import db
    conn = db.get_connection()
    for table in ("status_history", "reminders", "applications", "companies"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM settings WHERE key='sample_data_seeded'")
    conn.commit(); conn.close()
    db.set_setting("onboarding_complete", "1")      # an existing, set-up install
    db.init_db()                                    # a restart
    assert db.get_applications(include_archived=True) == []
    assert db.get_companies() == []


def test_company_years_are_not_capped_at_2027(client):
    import db
    db.add_application({"company": "Future Co", "job_desc": "Role", "status": "Submitted",
                        "date_applied": "2031-02-03"})
    company = [c for c in db.get_companies() if c["company_name"] == "Future Co"][0]
    assert company["applied_2031"] == 1                      # column added on demand
    conn = db.get_connection()
    assert "applied_2031" in db.applied_year_columns(conn)
    conn.close()
    # Editing the company keeps (and can change) the new year.
    db.update_company(company["id"], {"company_name": "Future Co", "applied_2031": "1",
                                      "applied_2025": "1"})
    company = db.get_company(company["id"])
    assert company["applied_2031"] == 1 and company["applied_2025"] == 1
    assert "applied_2031" in client.get("/export/companies").get_data(as_text=True).splitlines()[0]
    db.init_db()                                              # restart keeps working

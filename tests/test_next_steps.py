"""Next steps, calendar feed, phone sharing, saved job ads and attachments,
duplicate warnings, insights and auto-archive."""

import csv
import io
import json
import os
import re
from datetime import date, timedelta

import db
from app import _create_next_step_reminders, _auto_archive_finished_applications


def _add(company="Acme", role="Engineer", **fields):
    return db.add_application({"company": company, "job_desc": role, **fields})


def _day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _sql(statement, params=()):
    conn = db.get_connection()
    conn.execute(statement, params)
    conn.commit()
    conn.close()


# ── Next steps ───────────────────────────────────────────────────────────────

def test_next_step_is_saved_from_the_form_and_shown(client):
    client.post("/application/add", data={
        "company": "Acme", "job_desc": "Engineer", "status": "Submitted",
        "date_applied": _day(-3), "next_action": "Phone interview",
        "next_action_date": _day(2), "job_ad_text": "We are hiring, apply now.",
    })
    app = db.get_applications()[0]
    assert (app["next_action"], app["next_action_date"]) == ("Phone interview", _day(2))
    assert app["job_ad_text"] == "We are hiring, apply now."

    detail = client.get(f"/application/{app['id']}").get_data(as_text=True)
    assert "Phone interview" in detail and "We are hiring, apply now." in detail
    edit = client.get(f"/application/edit/{app['id']}").get_data(as_text=True)
    assert 'value="Phone interview"' in edit and f'value="{_day(2)}"' in edit


def test_dashboard_coming_up_lists_due_and_overdue_steps_only(client):
    _add("Overdue Co", next_action="Follow up", next_action_date=_day(-2))
    _add("Today Co", next_action="Interview", next_action_date=_day(0))
    _add("Later Co", next_action="Interview", next_action_date=_day(30))
    archived = _add("Archived Co", next_action="Follow up", next_action_date=_day(1))
    db.archive_application(archived)

    html = client.get("/").get_data(as_text=True)
    assert "Coming up" in html
    section = html.split("Coming up", 1)[1].split("Where they are now", 1)[0]
    assert section.index("Overdue Co") < section.index("Today Co")
    assert "overdue" in section and "Today" in section
    assert "Later Co" not in section and "Archived Co" not in section


def test_dashboard_hides_coming_up_without_next_steps(client):
    _add()
    assert "ml-upcoming" not in client.get("/").get_data(as_text=True)


def test_due_next_step_makes_one_inbox_reminder():
    app_id = _add(next_action="Send thank-you email", next_action_date=_day(0))
    _add("Later Co", next_action="Follow up", next_action_date=_day(3))
    _create_next_step_reminders()
    _create_next_step_reminders()
    reminders = [r for r in db.get_reminders() if r["reminder_type"] == "next_step"]
    assert len(reminders) == 1
    assert reminders[0]["application_id"] == app_id
    assert "Send thank-you email" in reminders[0]["message"] and "due today" in reminders[0]["message"]


# ── Calendar feed ────────────────────────────────────────────────────────────

def _calendar_link(client):
    client.post("/settings?section=general", data={"action": "calendar_create"})
    page = client.get("/settings?section=general").get_data(as_text=True)
    return re.search(r'id="calendarUrl"\s+value="([^"]+)"', page).group(1)


def test_calendar_feed_lists_next_steps(client):
    _add("Acme, Inc; Ltd", next_action="Interview", next_action_date="2026-11-05",
         link="https://example.com/job/1")
    _add("No date Co", next_action="Follow up")
    url = _calendar_link(client)
    assert url.startswith("http://localhost/calendar/") and url.endswith(".ics")

    response = client.get(url.replace("http://localhost", ""))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 1
    assert "DTSTART;VALUE=DATE:20261105" in body and "DTEND;VALUE=DATE:20261106" in body
    assert "SUMMARY:Interview — Acme\\, Inc\\; Ltd" in body
    assert all(len(line) <= 75 for line in body.split("\r\n"))


def test_calendar_feed_needs_the_right_token_but_no_login(client):
    url = _calendar_link(client).replace("http://localhost", "")
    db.set_setting("login_enabled", "1")
    assert client.get(url).status_code == 200
    assert client.get("/calendar/" + "x" * 32 + ".ics").status_code == 404
    db.set_setting("login_enabled", "0")

    client.post("/settings?section=general", data={"action": "calendar_remove"})
    assert client.get(url).status_code == 404


def test_new_calendar_link_replaces_the_old_one(client):
    old = _calendar_link(client).replace("http://localhost", "")
    new = _calendar_link(client).replace("http://localhost", "")
    assert old != new
    assert client.get(old).status_code == 404
    assert client.get(new).status_code == 200


# ── Share from the phone ─────────────────────────────────────────────────────

def test_manifest_accepts_shared_links(client):
    manifest = json.loads(client.get("/static/manifest.json").get_data(as_text=True))
    assert manifest["share_target"]["action"] == "/share"
    assert manifest["share_target"]["method"] == "GET"


def test_shared_link_prefills_the_add_form_once(client):
    response = client.get("/share", query_string={
        "title": "Graduate Engineer", "text": "Check out this job https://www.seek.com.au/job/123"})
    assert response.status_code == 302 and response.location.endswith("/application/add")
    page = client.get("/application/add").get_data(as_text=True)
    assert 'value="https://www.seek.com.au/job/123"' in page
    assert 'value="Graduate Engineer"' in page
    assert "Job link added from your share" in page
    assert "seek.com.au/job/123" not in client.get("/application/add").get_data(as_text=True)


def test_shared_link_already_saved_warns(client):
    _add("Acme", link="https://www.seek.com.au/job/123", status="Submitted")
    client.get("/share", query_string={"url": "https://www.seek.com.au/job/123"})
    page = client.get("/application/add").get_data(as_text=True)
    assert "You already have this job saved: Acme (Submitted)" in page


def test_share_survives_logging_in(client):
    db.set_setting("login_enabled", "1")
    try:
        client.get("/share", query_string={"url": "https://example.com/job"})
        assert client.get("/application/add").status_code == 302   # off to log in first
        with client.session_transaction() as session:
            assert session["share_prefill"]["link"] == "https://example.com/job"
    finally:
        db.set_setting("login_enabled", "0")


# ── Duplicate warning ────────────────────────────────────────────────────────

def test_same_role_within_60_days_is_a_possible_duplicate():
    _add("Acme", "Engineer", date_applied="2026-08-01", status="Rejected")
    assert db.find_duplicate_applications(" acme ", "ENGINEER", "2026-09-15")
    assert db.find_duplicate_applications("Acme", "Engineer", "2026-07-01")
    assert not db.find_duplicate_applications("Acme", "Engineer", "2026-11-01")
    assert not db.find_duplicate_applications("Acme", "Engineer", "2026-09-15", team="Mining")


def test_same_link_is_a_possible_duplicate_even_for_another_role():
    _add("Acme", "Engineer", date_applied="2025-01-01", link="https://example.com/job/9")
    found = db.find_duplicate_applications("Beta", "Analyst", "2026-10-01",
                                           link=" https://example.com/job/9 ")
    assert [d["reason"] for d in found] == ["link"]


def test_archived_applications_still_count_as_duplicates():
    app_id = _add("Acme", "Engineer", date_applied="2026-10-01", status="Rejected")
    db.archive_application(app_id)
    assert db.find_duplicate_applications("Acme", "Engineer", "2026-10-20")


def test_add_form_explains_the_duplicate_and_add_anyway_works(client):
    _add("Acme", "Engineer", date_applied="2026-10-01", status="Submitted")
    form = {"company": "Acme", "job_desc": "Engineer", "date_applied": "2026-10-20",
            "status": "Submitted"}
    page = client.post("/application/add", data=form).get_data(as_text=True)
    assert "You may have applied for this already" in page
    assert "Same company and role within 60 days." in page
    assert len(db.get_applications()) == 1

    client.post("/application/add", data={**form, "force_add": "1"})
    assert len(db.get_applications()) == 2


# ── Attachments ──────────────────────────────────────────────────────────────

def _upload(client, app_id, name="cv.pdf", data=b"%PDF-1.4 my cv", kind="CV / resume"):
    return client.post(f"/application/{app_id}/attachments",
                       data={"kind": kind, "file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def test_attach_download_and_remove_a_file(client):
    app_id = _add()
    _upload(client, app_id)
    files = db.get_attachments(app_id)
    assert [(f["filename"], f["kind"], f["size"]) for f in files] == [("cv.pdf", "CV / resume", 14)]
    stored = db.attachment_path(files[0]["stored_name"])
    assert os.path.exists(stored) and not stored.endswith("cv.pdf")

    detail = client.get(f"/application/{app_id}").get_data(as_text=True)
    assert "cv.pdf" in detail
    download = client.get(f"/attachments/{files[0]['id']}")
    assert download.get_data() == b"%PDF-1.4 my cv"
    assert "cv.pdf" in download.headers["Content-Disposition"]
    download.close()

    client.post(f"/attachments/{files[0]['id']}/delete")
    assert db.get_attachments(app_id) == []
    assert not os.path.exists(stored)


def test_attachment_type_and_size_are_checked(client, monkeypatch):
    app_id = _add()
    page = _upload(client, app_id, name="run.exe", data=b"MZ")
    assert page.status_code == 302
    monkeypatch.setattr(db, "MAX_ATTACHMENT_BYTES", 10)
    _upload(client, app_id, name="big.pdf", data=b"x" * 11)
    assert db.get_attachments(app_id) == []


def test_deleting_an_application_deletes_its_files(client):
    app_id = _add()   # undated: deleting it used to crash building the year link
    _upload(client, app_id)
    stored = db.attachment_path(db.get_attachments(app_id)[0]["stored_name"])
    client.post(f"/application/delete/{app_id}")
    assert not os.path.exists(stored)


def test_attachments_of_another_user_are_hidden(client):
    app_id = db.add_application({"company": "Theirs", "job_desc": "Role"}, user_id=99)
    attachment_id = db.add_attachment(app_id, "cv.pdf", b"data")
    assert db.get_attachment(attachment_id, user_id=1) is None
    assert db.get_attachment(attachment_id, user_id=99) is not None


# ── Insights ─────────────────────────────────────────────────────────────────

def test_insights_rates_by_channel(client):
    interviewed = _add("A", how_applied="Email", date_applied="2026-09-01", status="Submitted",
                       industry="Mining, Engineering")
    db.update_application(interviewed, {**db.get_application(interviewed), "status": "Interview_Scheduled"})
    db.update_application(interviewed, {**db.get_application(interviewed), "status": "Rejected"})
    _sql("UPDATE status_history SET changed_at='2026-09-11T09:00:00' "
         "WHERE application_id=? AND status='Interview_Scheduled'", (interviewed,))
    _add("B", how_applied="Email", date_applied="2026-09-02", status="Submitted", industry="Mining")
    _add("C", how_applied="", date_applied="2026-09-03", status="Awaiting_Response")
    _add("Late entry", how_applied="Phone", date_applied="2026-01-01", status="Rejected")
    _add("D", date_applied="2026-09-04", status="Drafting_CV")           # not sent: left out

    result = db.get_insights()
    assert result["overall"]["sent"] == 4
    assert result["overall"]["heard_back"] == 2 and result["overall"]["progressed"] == 1
    # "Late entry" was added already rejected, so it has no reply time.
    assert result["overall"]["median_reply_days"] == 10

    channels = {r["name"]: r for r in result["by_channel"]}
    assert channels["Email"]["sent"] == 2 and channels["Email"]["heard_back_pct"] == 50
    assert channels["Not recorded"]["sent"] == 1
    assert result["by_channel"][-1]["name"] == "Not recorded"
    industries = {r["name"]: r["sent"] for r in result["by_industry"]}
    assert industries == {"Mining": 2, "Engineering": 1, "Not recorded": 2}

    page = client.get("/insights").get_data(as_text=True)
    assert "By how you applied" in page and "Email" in page and "50%" in page
    assert client.get("/insights?year=2026").status_code == 200


def test_insights_empty_state(client):
    page = client.get("/insights").get_data(as_text=True)
    assert "Nothing to compare yet." in page
    assert 'href="/insights"' in client.get("/").get_data(as_text=True)


# ── Auto-archive ─────────────────────────────────────────────────────────────

def test_auto_archive_moves_old_finished_applications():
    old_rejected = _add("Old", status="Rejected", date_applied=_day(-90))
    new_rejected = _add("New", status="Rejected", date_applied=_day(-90))
    old_submitted = _add("Waiting", status="Submitted", date_applied=_day(-90))
    _sql("UPDATE applications SET status_changed_at=? WHERE id IN (?, ?)",
         (_day(-40) + "T10:00:00", old_rejected, old_submitted))

    db.set_setting("auto_archive_days", "0")
    _auto_archive_finished_applications()
    assert not db.get_application(old_rejected)["archived"]

    db.set_setting("auto_archive_days", "30")
    try:
        _auto_archive_finished_applications()
    finally:
        db.set_setting("auto_archive_days", "0")
    assert db.get_application(old_rejected)["archived"] == 1
    assert not db.get_application(new_rejected)["archived"]
    assert not db.get_application(old_submitted)["archived"]


def test_auto_archive_setting_is_saved_and_checked(client):
    base = {"action": "save_general", "reminder_days": "3", "stale_threshold_value": "2",
            "rejected_threshold_value": "4", "check_interval": "1h"}
    try:
        client.post("/settings?section=general", data={**base, "auto_archive_days": "45"})
        assert db.get_setting("auto_archive_days") == "45"
        page = client.post("/settings?section=general", data={**base, "auto_archive_days": "-1"},
                           follow_redirects=True).get_data(as_text=True)
        assert "Auto-archive days must be a whole number" in page
        assert db.get_setting("auto_archive_days") == "45"
    finally:
        db.set_setting("auto_archive_days", "0")


# ── CSV ──────────────────────────────────────────────────────────────────────

def test_csv_export_and_import_carry_the_new_fields(client):
    _add(next_action="Follow up", next_action_date="2026-11-05", job_ad_text="The ad")
    exported = client.get("/export/applications").get_data(as_text=True)
    row = next(csv.DictReader(io.StringIO(exported)))
    assert (row["next_action"], row["next_action_date"], row["job_ad_text"]) == \
        ("Follow up", "2026-11-05", "The ad")

    result = db.bulk_import_applications([{"company": "Beta", "job_desc": "Analyst",
                                            "next_action": "Interview",
                                            "next_action_date": "07/11/2026"}])
    assert result["imported"] == 1
    beta = [a for a in db.get_applications() if a["company"] == "Beta"][0]
    assert (beta["next_action"], beta["next_action_date"]) == ("Interview", "2026-11-07")

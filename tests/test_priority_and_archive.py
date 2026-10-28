"""Restoring archived applications, priorities and the insights charts."""

from datetime import date, timedelta

import db
from app import _auto_archive_finished_applications


def _add(company="Acme", role="Engineer", **fields):
    return db.add_application({"company": company, "job_desc": role, **fields})


def _day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _sql(statement, params=()):
    conn = db.get_connection()
    conn.execute(statement, params)
    conn.commit()
    conn.close()


# ── Restoring from the archive ───────────────────────────────────────────────

def test_archived_application_can_be_restored_from_its_page(client):
    app_id = _add(status="Rejected", date_applied=_day(-10))
    db.archive_application(app_id)

    page = client.get(f"/application/{app_id}").get_data(as_text=True)
    assert "Restore" in page and "Archived on" in page

    resp = client.post(f"/application/unarchive/{app_id}")
    assert resp.status_code == 302 and resp.location.endswith(f"/application/{app_id}")
    restored = db.get_application(app_id)
    assert not restored["archived"] and restored["unarchived_at"]


def test_restore_returns_to_the_page_it_was_pressed_on(client):
    app_id = _add(status="Rejected")
    db.archive_application(app_id)
    resp = client.post(f"/application/unarchive/{app_id}", data={"next": "/year/2026?show=archived"})
    assert resp.location.endswith("/year/2026?show=archived")
    db.archive_application(app_id)
    resp = client.post(f"/application/unarchive/{app_id}", data={"next": "https://evil.example/"})
    assert resp.location.endswith(f"/application/{app_id}")


def test_year_view_lists_archived_applications_separately(client):
    year = date.today().year
    kept = _add("Kept Co", status="Submitted", date_applied=_day(0))
    gone = _add("Gone Co", status="Rejected", date_applied=_day(0))
    db.archive_application(gone)

    current = client.get(f"/year/{year}").get_data(as_text=True)
    assert "Kept Co" in current and "Gone Co" not in current and "Archived (1)" in current

    archived = client.get(f"/year/{year}?show=archived").get_data(as_text=True)
    assert "Gone Co" in archived and "Kept Co" not in archived
    assert f"/application/unarchive/{gone}" in archived
    assert kept


def test_auto_archive_leaves_a_restored_application_alone():
    app_id = _add(status="Rejected", date_applied=_day(-90))
    _sql("UPDATE applications SET status_changed_at=? WHERE id=?", (_day(-60) + "T10:00:00", app_id))
    db.set_setting("auto_archive_days", "30")
    try:
        _auto_archive_finished_applications()
        assert db.get_application(app_id)["archived"] == 1
        db.unarchive_application(app_id)
        _auto_archive_finished_applications()
        assert not db.get_application(app_id)["archived"]
        # A month after being restored it's fair game again.
        _sql("UPDATE applications SET unarchived_at=? WHERE id=?", (_day(-31) + "T10:00:00", app_id))
        _auto_archive_finished_applications()
        assert db.get_application(app_id)["archived"] == 1
    finally:
        db.set_setting("auto_archive_days", "0")


# ── Priority ─────────────────────────────────────────────────────────────────

def test_parse_priority_reads_words_and_numbers():
    assert [db.parse_priority(v) for v in ("High", "medium", "L", "", None, "3", "0", 2.0)] == \
        [3, 2, 1, 0, 0, 3, 0, 2]
    assert db.parse_priority("urgent") is None and db.parse_priority("7") is None


def test_priority_is_saved_from_the_form_and_kept_when_not_sent(client):
    client.post("/application/add", data={"company": "Acme", "job_desc": "Engineer",
                                          "status": "Submitted", "priority": "3"})
    app = db.get_applications()[0]
    assert app["priority"] == 3
    client.post(f"/application/edit/{app['id']}", data={"company": "Acme", "job_desc": "Engineer",
                                                        "status": "Submitted", "priority": "1"})
    assert db.get_application(app["id"])["priority"] == 1
    # Callers that don't send a priority (e.g. import updates) leave it alone.
    db.update_application(app["id"], {"company": "Acme", "job_desc": "Engineer", "status": "Submitted"})
    assert db.get_application(app["id"])["priority"] == 1


def test_year_view_sorts_by_priority_by_default(client):
    year = date.today().year
    _add("Low Co", status="Submitted", date_applied=_day(0), priority=1)
    _add("High Co", status="Submitted", date_applied=_day(-20), priority=3)
    _add("Unset Co", status="Submitted", date_applied=_day(-1))
    _add("Done Co", status="Rejected", date_applied=_day(-2), priority=3)
    _add("Soon Co", status="Submitted", date_applied=_day(-30), priority=1, next_action_date=_day(1))

    html = client.get(f"/year/{year}").get_data(as_text=True)
    order = sorted(["Low Co", "High Co", "Unset Co", "Done Co", "Soon Co"], key=html.index)
    assert order == ["High Co", "Soon Co", "Low Co", "Unset Co", "Done Co"]

    # The other sorts are unchanged; priority only applies when chosen (the default).
    by_date = client.get(f"/year/{year}?sort=date").get_data(as_text=True)
    assert by_date.index("High Co") > by_date.index("Soon Co")
    assert '<option value="date" selected>' in by_date


def test_priority_menu_and_bulk_set(client):
    year = date.today().year
    a = _add("A Co", status="Submitted", date_applied=_day(0))
    b = _add("B Co", status="Submitted", date_applied=_day(0))
    resp = client.post(f"/application/{a}/priority", data={"priority": "2", "next": f"/year/{year}?sort=date"})
    assert resp.location.endswith(f"/year/{year}?sort=date")
    assert db.get_application(a)["priority"] == 2
    assert client.post(f"/application/{a}/priority", data={"priority": "9"}).status_code == 302
    assert db.get_application(a)["priority"] == 2

    client.post("/applications/bulk-action", data={"action": "set_priority", "bulk_priority": "3",
                                                   "selected_ids": [a, b], "year": year})
    assert {db.get_application(i)["priority"] for i in (a, b)} == {3}


def test_priority_round_trips_through_csv(client):
    _add("Csv Co", priority=3)
    exported = client.get("/export/applications").get_data(as_text=True)
    header, row = exported.splitlines()[:2]
    assert "priority" in header.split(",") and row.split(",")[header.split(",").index("priority")] == "3"
    from db.applications import _clean_import_row
    warnings: list = []
    assert _clean_import_row({"priority": "Medium"}, "Row 2", set(), warnings)["priority"] == 2
    assert _clean_import_row({"priority": "asap"}, "Row 3", set(), warnings)["priority"] == 0
    assert warnings == ["Row 3: could not read priority 'asap' — left unset."]


# ── Insights: where applications went ────────────────────────────────────────

def _history(app_id, *statuses):
    for status in statuses:
        _sql("INSERT INTO status_history (application_id, status, changed_at) VALUES (?,?,?)",
             (app_id, status, "2026-01-01T00:00:00"))


def test_application_flow_follows_each_application_to_its_outcome():
    _add("Draft", status="Drafting_CV", date_applied="2025-03-01")
    _add("Skipped", status="Not_Applying", date_applied="2025-03-01")
    _add("Waiting", status="Submitted", date_applied="2025-03-01")
    ghosted = _add("Ghosted", status="Job_Expired", date_applied="2025-03-01")
    _history(ghosted, "Submitted")
    _add("Quick no", status="Rejected", date_applied="2025-03-01")
    offer = _add("Offer", status="Offer_Received", date_applied="2025-03-01")
    _history(offer, "Interview_Scheduled")
    late_no = _add("Late no", status="Rejected", date_applied="2025-03-01")
    _history(late_no, "Online_Assessment")
    db.archive_application(late_no)
    withdrew = _add("Withdrew", status="Not_Applying", date_applied="2025-03-01")
    _history(withdrew, "Interview_Scheduled")
    _add("This year", status="Submitted", date_applied=_day(0))

    flow = db.get_application_flow(year=2025)
    value = {n["id"]: n["value"] for n in flow["nodes"]}
    assert flow["total"] == 8 and flow["archived"] == 1
    assert value == {"all": 8, "not_sent": 2, "drafting": 1, "not_applying": 1,
                     "sent": 6, "no_reply": 2, "waiting": 1, "closed_no_reply": 1,
                     "heard": 4, "rejected_early": 1, "progressed": 3,
                     "offer": 1, "rejected_late": 1, "ended_other": 1}
    links = {(l["source"], l["target"]): l["value"] for l in flow["links"]}
    assert links[("all", "sent")] == 6 and links[("heard", "progressed")] == 3
    outcomes = {o["key"]: o["value"] for o in flow["outcomes"]}
    assert outcomes == {"offer": 1, "waiting": 1, "rejected": 2, "not_sent": 4}

    # All years includes last year and this year.
    assert db.get_application_flow()["total"] == 9


def test_insights_page_shows_the_charts(client):
    _add("Draft only", status="Drafting_CV", date_applied=_day(0))
    page = client.get("/insights").get_data(as_text=True)
    assert 'id="outcomeChart"' in page and 'id="flowChart"' in page
    assert "INSIGHTS_CONFIG" in page and "js/insights.js" in page
    assert "Still drafting" in page  # table view of the flow
    db.get_connection().close()


def test_insights_page_without_applications_shows_the_empty_state(client):
    page = client.get("/insights").get_data(as_text=True)
    assert "Nothing to compare yet." in page and 'id="flowChart"' not in page

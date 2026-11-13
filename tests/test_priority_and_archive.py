import re
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


def test_year_view_priority_sort(client):
    year = date.today().year
    _add("Low Co", status="Submitted", date_applied=_day(0), priority=1)
    _add("High Co", status="Submitted", date_applied=_day(-20), priority=3)
    _add("Unset Co", status="Submitted", date_applied=_day(-1))
    _add("Done Co", status="Rejected", date_applied=_day(-2), priority=3)
    _add("Soon Co", status="Submitted", date_applied=_day(-30), priority=1, next_action_date=_day(1))

    html = client.get(f"/year/{year}?sort=priority").get_data(as_text=True)
    order = sorted(["Low Co", "High Co", "Unset Co", "Done Co", "Soon Co"], key=html.index)
    assert order == ["High Co", "Soon Co", "Low Co", "Unset Co", "Done Co"]

    # Newest first is really newest first (applied 20 days ago before 30 days ago).
    by_date = client.get(f"/year/{year}?sort=date").get_data(as_text=True)
    assert by_date.index("Low Co") < by_date.index("Unset Co") < by_date.index("High Co") < by_date.index("Soon Co")
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
    assert "Saved or drafting" in page  # table view of the flow
    # Too wide for phones: the flow card is hidden below the md breakpoint.
    assert 'class="col-lg-7 d-none d-md-block"' in page
    db.get_connection().close()


def test_insights_page_without_applications_shows_the_empty_state(client):
    page = client.get("/insights").get_data(as_text=True)
    assert "Nothing to compare yet." in page and 'id="flowChart"' not in page


def test_application_page_has_a_back_arrow_top_left(client):
    app_id = _add(date_applied="2025-05-01")
    page = client.get(f"/application/{app_id}").get_data(as_text=True)
    arrow = page.index('class="ml-back-btn"')
    assert arrow < page.index("<h2") and 'href="/year/2025"' in page[arrow - 200:arrow]
    undated = _add("Undated Co")
    assert 'href="/"\n       class="ml-back-btn"' in client.get(f"/application/{undated}").get_data(as_text=True)


# ── Saved status and the status sort ─────────────────────────────────────────

def test_new_applications_start_as_saved(client):
    form = client.get("/application/add").get_data(as_text=True)
    assert re.search(r'<option value="Saved"\s+selected', form)
    assert not re.search(r'<option value="Select_Status"\s+selected', form)
    result = db.bulk_import_applications([
        {"company": "No Status Co", "job_desc": "Role"},
        {"company": "Odd Status Co", "job_desc": "Role", "status": "Pending_Thing"},
    ])
    assert result["imported"] == 2
    statuses = {a["company"]: a["status"] for a in db.get_applications()}
    assert statuses == {"No Status Co": "Saved", "Odd Status Co": "Saved"}
    assert any("set to Saved" in w for w in result["warnings"])


def test_saved_status_is_added_to_an_existing_database_after_no_status(client):
    conn = db.get_connection()
    conn.execute("DELETE FROM statuses WHERE name='Saved'")
    conn.commit(); conn.close()
    assert "Saved" not in db.get_status_options()
    db.init_db()
    order = db.get_status_options()
    assert order.index("Saved") == order.index("Select_Status") + 1
    assert len(order) == len(set(order))
    ok, _ = db.delete_status("Saved")
    assert not ok                                   # it is the default, so it stays


def test_year_view_shows_interviews_first_by_default(client):
    year = date.today().year
    _add("Applied Co", status="Submitted", date_applied=_day(0), priority=3)
    _add("Saved Co", status="Saved", date_applied=_day(-1))
    _add("Draft Co", status="Drafting_Application", date_applied=_day(-2))
    _add("Task Co", status="Online_Assessment", date_applied=_day(-3))
    _add("Interview Co", status="Interview_Scheduled", date_applied=_day(-9))
    _add("Rejected Co", status="Rejected", date_applied=_day(-1), priority=3)
    _add("Offer Co", status="Offer_Received", date_applied=_day(-20))
    _add("Waiting Co", status="Awaiting_Response", date_applied=_day(-4))

    names = ["Applied Co", "Saved Co", "Draft Co", "Task Co", "Interview Co",
             "Rejected Co", "Offer Co", "Waiting Co"]
    expected = ["Offer Co", "Interview Co", "Task Co", "Draft Co", "Saved Co",
                "Applied Co", "Waiting Co", "Rejected Co"]
    for url in (f"/year/{year}", f"/year/{year}?sort=status"):
        html = client.get(url).get_data(as_text=True)
        assert sorted(names, key=html.index) == expected, url
    assert '<option value="status" selected>' in client.get(f"/year/{year}").get_data(as_text=True)


def test_status_sort_places_custom_statuses_by_name():
    assert db.status_rank("Second_Interview") == db.status_rank("Interview_Scheduled")
    assert db.status_rank("Take_Home_Assignment") == db.status_rank("Online_Assessment")
    assert db.status_rank("Drafting_Cover_Letter") == db.status_rank("Drafting_CV")
    assert db.status_rank("Submitted") < db.status_rank("Recruiter_Call") < db.status_rank("Rejected")


def test_expressions_of_interest_have_their_own_view(client):
    year = date.today().year
    _add("Main Co", status="Submitted", date_applied=_day(0))
    _add("Eoi Co", status="EOI", date_applied=_day(-1))
    main = client.get(f"/year/{year}").get_data(as_text=True)
    assert "Main Co" in main and "Eoi Co" not in main
    assert "Expressions of interest (1)" in main
    eoi = client.get(f"/year/{year}?show=eoi").get_data(as_text=True)
    assert "Eoi Co" in eoi and "Main Co" not in eoi
    assert '<option value="eoi" selected>' in eoi
    # Picking EOI in the status filter lands in the same view.
    assert "Eoi Co" in client.get(f"/year/{year}?status=EOI").get_data(as_text=True)
    # EOI sorts last wherever statuses are ranked.
    assert db.status_rank("EOI") > db.status_rank("Rejected")


# ── Stale rule ───────────────────────────────────────────────────────────────

def _stale(status, quiet_days, **extra):
    app = {"status": status, "date_applied": _day(-60),
           "status_changed_at": _day(-quiet_days), **extra}
    return db.applications._enrich(app, 14)["is_stale"]


def test_stale_depends_on_the_stage():
    assert _stale("Submitted", 15) and not _stale("Submitted", 14)          # Settings: 2 weeks
    assert _stale("Awaiting_Response", 20)
    assert _stale("Interview_Scheduled", 8) and not _stale("Interview_Scheduled", 7)
    assert _stale("Online_Assessment", 8)
    assert _stale("Drafting_Application", 8) and not _stale("Drafting_Application", 3)
    for never in ("Saved", "Select_Status", "EOI", "Rejected", "Likely_Rejected", "Job_Expired"):
        assert not _stale(never, 200), never


def test_contact_or_a_booked_next_step_keeps_it_fresh():
    assert not _stale("Submitted", 30, last_contact_date=_day(-2))
    assert not _stale("Interview_Scheduled", 30, next_action_date=_day(3))
    assert _stale("Interview_Scheduled", 30, next_action_date=_day(-3))     # overdue step
    assert not _stale("Submitted", 30, archived=1)


def test_newest_first_is_not_reordered_by_stale(client):
    year = date.today().year
    _add("Old Draft Co", status="Drafting_Application", date_applied=_day(-40))
    _add("Fresh Co", status="Submitted", date_applied=_day(0))
    html = client.get(f"/year/{year}?sort=date").get_data(as_text=True)
    assert html.index("Fresh Co") < html.index("Old Draft Co")


def test_check_in_reminders_use_the_same_rule():
    a = _add("Quiet Co", status="Submitted", date_applied=_day(-30))
    b = _add("Booked Co", status="Interview_Scheduled", date_applied=_day(-30),
             next_action_date=_day(2))
    c = _add("Drafty Co", status="Drafting_Application", date_applied=_day(-30))
    conn = db.get_connection()
    conn.execute("UPDATE applications SET status_changed_at=?", (_day(-30),))
    conn.commit(); conn.close()
    found = {x["company"] for x in db.get_stalled_submitted_applications(14)}
    assert found == {"Quiet Co"}          # booked interview and drafts get no HR check-in


def test_dashboard_status_board_counts_archived_applications(client):
    live = _add("Live Co", status="Rejected", date_applied=_day(0))
    gone = _add("Gone Co", status="Rejected", date_applied=_day(0))
    old = _add("Old Co", status="Job_Expired", date_applied=_day(0))
    db.archive_application(gone)
    db.archive_application(old)
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'aria-label="2 Rejected"', html)                 # 1 live + 1 archived
    assert "(1 archived)" in html
    # A status whose applications are all archived links to the archive view.
    assert re.search(r'href="/year/\d+\?status=Job_Expired&amp;show=archived"', html)


def test_dashboard_counts_include_archived_and_offers_are_counted_right():
    year = date.today().year
    _add("Live Co", status="Submitted", date_applied=_day(0))
    old = _add("Old Co", status="Rejected", date_applied=_day(0))
    db.archive_application(old)
    _add("Said No Co", status="Offer_Rejected", date_applied=_day(0))
    _add("Interview Co", status="Interview_Scheduled", date_applied=_day(-5))
    _add("Eoi Co", status="EOI", date_applied=_day(0))
    stats = db.get_stats(year=year)
    assert stats["total"] == 5                     # archived ones count
    assert stats["rejected"] == 1                  # declining an offer isn't a rejection
    assert stats["offers"] == 1                    # but it was an offer
    # In progress: no archived, no EOI, most urgent first.
    assert [a["company"] for a in stats["pending"]] == ["Interview Co", "Live Co"]


def test_quick_status_contact_and_needs_attention(client):
    year = date.today().year
    quiet = _add("Quiet Co", status="Submitted", date_applied=_day(-40))
    _add("Fresh Co", status="Submitted", date_applied=_day(0))
    conn = db.get_connection()
    conn.execute("UPDATE applications SET status_changed_at=? WHERE id=?", (_day(-40), quiet))
    conn.commit(); conn.close()

    page = client.get(f"/year/{year}?show=stale").get_data(as_text=True)
    assert "Needs attention (1)" in page and "Quiet Co" in page and "Fresh Co" not in page
    assert f'/application/{quiet}/contacted' in page and f'/application/{quiet}/status' in page

    # One tap: contacted today -> no longer stale.
    nxt = f"/year/{year}?show=stale"
    assert client.post(f"/application/{quiet}/contacted", data={"next": nxt}).location.endswith(nxt)
    assert db.get_application(quiet)["last_contact_date"] == date.today().isoformat()
    assert "Needs attention (0)" in client.get(f"/year/{year}").get_data(as_text=True)

    # Quick status change goes into the history; nonsense statuses are refused.
    client.post(f"/application/{quiet}/status", data={"status": "Interview_Scheduled"})
    assert db.get_application(quiet)["status"] == "Interview_Scheduled"
    assert db.get_application_timeline(quiet)[-1]["status"] == "Interview_Scheduled"
    client.post(f"/application/{quiet}/status", data={"status": "Made_Up"})
    assert db.get_application(quiet)["status"] == "Interview_Scheduled"


def test_old_style_dates_are_fixed_so_the_year_shows():
    a = _add("Slash Co", status="Rejected")
    b = _add("Odd Co", status="Rejected")
    conn = db.get_connection()
    conn.execute("UPDATE applications SET date_applied='10/03/2025' WHERE id=?", (a,))
    conn.execute("UPDATE applications SET date_applied='sometime' WHERE id=?", (b,))
    conn.commit(); conn.close()
    assert 2025 not in db.get_dynamic_years()
    db.init_db()
    assert db.get_application(a)["date_applied"] == "2025-03-10"
    assert db.get_application(b)["date_applied"] == "sometime"      # unreadable: left alone
    assert 2025 in db.get_dynamic_years()


def test_past_years_open_with_archived_applications_too(client):
    last = date.today().year - 1
    done = _add("Old Rejected Co", status="Rejected", date_applied=f"{last}-03-01")
    db.archive_application(done)
    _add("Old Open Co", status="Submitted", date_applied=f"{last}-04-01")
    page = client.get(f"/year/{last}").get_data(as_text=True)
    assert "Old Rejected Co" in page and "Old Open Co" in page
    assert '<option value="all" selected>' in page and "ml-row-archived" in page
    # The current year still opens on what's going, with All one click away.
    this = client.get(f"/year/{date.today().year}").get_data(as_text=True)
    assert '<option value="current" selected>' in this
    current_only = client.get(f"/year/{last}?show=current").get_data(as_text=True)
    assert "Old Rejected Co" not in current_only and "Old Open Co" in current_only

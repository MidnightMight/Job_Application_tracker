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

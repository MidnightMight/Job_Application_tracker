"""Tests for db.bulk_import_applications and the import column guesser."""

import csv
import io

import db
from db.applications import IMPORTABLE_FIELDS
from routes.import_ import _guess_mapping


def _row(**kwargs):
    base = {"company": "Acme", "job_desc": "Graduate Engineer"}
    base.update(kwargs)
    return base


def _only_app():
    apps = db.get_applications(include_archived=True)
    assert len(apps) == 1
    return apps[0]


def test_date_applied_is_optional():
    result = db.bulk_import_applications([_row(date_applied="")])
    assert result["imported"] == 1
    assert result["errors"] == []
    assert not _only_app()["date_applied"]


def test_day_first_and_timestamp_dates_are_normalised():
    db.bulk_import_applications([
        _row(date_applied="26/10/2026"),
        _row(company="Beta", date_applied="2026-10-27T09:30:00"),
    ])
    dates = sorted(a["date_applied"] for a in db.get_applications(include_archived=True))
    assert dates == ["2026-10-26", "2026-10-27"]


def test_unreadable_date_is_a_warning_not_garbage():
    result = db.bulk_import_applications([_row(date_applied="next tuesday")])
    assert result["imported"] == 1
    assert any("date_applied" in w for w in result["warnings"])
    assert not _only_app()["date_applied"]


def test_zero_flags_stay_zero():
    # Regression: the string "0" used to be treated as truthy.
    db.bulk_import_applications([_row(cover_letter="0", resume="0")])
    app = _only_app()
    assert app["cover_letter"] == 0
    assert app["resume"] == 0


def test_resume_defaults_to_yes_when_column_missing():
    db.bulk_import_applications([_row()])
    assert _only_app()["resume"] == 1


def test_job_expiry_date_is_imported():
    db.bulk_import_applications([_row(job_expiry_date="02/11/2026")])
    assert _only_app()["job_expiry_date"] == "2026-11-02"


def test_unknown_status_falls_back_with_warning():
    result = db.bulk_import_applications([_row(status="Banana")])
    assert _only_app()["status"] == "Saved"
    assert any("Banana" in w and "Saved" in w for w in result["warnings"])


def test_row_without_company_or_role_is_skipped():
    result = db.bulk_import_applications([{"company": "", "job_desc": ""}])
    assert result["imported"] == 0
    assert result["other_skipped"] == 1


def test_duplicates_skipped_by_default():
    rows = [_row(date_applied="2026-10-01")]
    db.bulk_import_applications(rows)
    result = db.bulk_import_applications(rows)
    assert result["imported"] == 0
    assert result["duplicates"] == 1


def test_undated_duplicates_are_detected():
    db.bulk_import_applications([_row()])
    result = db.bulk_import_applications([_row()])
    assert result["duplicates"] == 1


def test_update_existing_by_id_changes_only_mapped_fields():
    db.bulk_import_applications([_row(date_applied="2026-10-01", status="Submitted",
                                      comment="keep me")])
    app_id = _only_app()["id"]
    result = db.bulk_import_applications(
        [{"id": str(app_id), "status": "Rejected"}], update_existing=True,
    )
    assert result["updated"] == 1 and result["imported"] == 0
    app = _only_app()
    assert app["status"] == "Rejected"
    assert app["comment"] == "keep me"
    assert app["company"] == "Acme"


def test_update_existing_by_matching_key():
    db.bulk_import_applications([_row(date_applied="2026-10-01")])
    result = db.bulk_import_applications(
        [_row(date_applied="2026-10-01", status="Submitted")], update_existing=True,
    )
    assert result["updated"] == 1
    assert _only_app()["status"] == "Submitted"


def test_unknown_id_with_update_inserts_new_row():
    result = db.bulk_import_applications([_row(id="99999")], update_existing=True)
    assert result["imported"] == 1


def test_status_change_via_update_is_recorded_in_history():
    db.bulk_import_applications([_row(date_applied="2026-10-01", status="Submitted")])
    app_id = _only_app()["id"]
    db.bulk_import_applications([{"id": str(app_id), "status": "Rejected"}],
                                update_existing=True)
    statuses = [h["status"] for h in db.get_application_timeline(app_id)]
    assert statuses == ["Submitted", "Rejected"]


def test_guess_mapping_prefers_exact_export_headers():
    headers = ["id", "company", "job_desc", "team", "date_applied", "status",
               "cover_letter", "resume", "duration", "success_chance", "link",
               "contact", "comment", "additional_notes", "job_expiry_date",
               "industry", "last_modified_at"]
    guessed = _guess_mapping(headers)
    mapping = dict(zip(headers, guessed))
    assert mapping["id"] == "id"
    assert mapping["job_expiry_date"] == "job_expiry_date"
    assert mapping["date_applied"] == "date_applied"
    assert mapping["duration"] == ""
    assert mapping["last_modified_at"] == ""
    # No field is suggested twice.
    used = [g for g in guessed if g]
    assert len(used) == len(set(used))


def test_export_then_reimport_with_update_creates_no_duplicates(client):
    db.bulk_import_applications([
        _row(date_applied="2026-10-01", status="Submitted"),
        _row(company="Beta", date_applied=""),
    ])
    exported = client.get("/export/applications").get_data(as_text=True)
    rows = list(csv.DictReader(io.StringIO(exported)))
    for r in rows:
        r["status"] = "Rejected"
    rows = [{k: v for k, v in r.items() if k in ("id",) + IMPORTABLE_FIELDS} for r in rows]
    result = db.bulk_import_applications(rows, update_existing=True)
    assert result["updated"] == 2 and result["imported"] == 0
    assert {a["status"] for a in db.get_applications(include_archived=True)} == {"Rejected"}


def test_map_page_submits_its_own_form_when_logged_in(client):
    """With login on, the menu's Log out form comes first on the page; the Import
    button's script must submit the import form, not the first POST form."""
    from werkzeug.security import generate_password_hash
    db.set_setting("login_enabled", "1")
    try:
        if not db.get_user_by_username("importer"):
            db.add_user("importer", generate_password_hash("pw"), is_admin=True)
        client.post("/login", data={"username": "importer", "password": "pw"})
        page = client.post(
            "/application/import",
            data={"csv_file": (io.BytesIO(b"Company,Role\nAcme,Tester\n"), "jobs.csv")},
            content_type="multipart/form-data",
        ).get_data(as_text=True)
        assert 'action="/logout"' in page
        assert '<form method="post" id="importForm">' in page
        assert "getElementById('importForm')" in page
        assert "querySelector('form[method=\"post\"]')" not in page
    finally:
        db.set_setting("login_enabled", "0")


def test_everyday_status_words_are_recognised():
    rows = [_row(company=f"Co {i}", status=word) for i, word in enumerate(
        ["Applied", "interview scheduled", "Phone screen", "Ghosted", "Offer", "withdrawn",
         "ONLINE_ASSESSMENT", "Unsuccessful", "Wishlist", "Ghosted-ish"])]
    result = db.bulk_import_applications(rows)
    got = [a["status"] for a in sorted(db.get_applications(), key=lambda a: int(a["company"][3:]))]
    assert got == ["Submitted", "Interview_Scheduled", "Interview_Scheduled", "Likely_Rejected",
                   "Offer_Received", "Not_Applying", "Online_Assessment", "Rejected", "Saved",
                   "Saved"]
    # Only the word nobody could guess gets a warning.
    assert [w for w in result["warnings"] if "unknown status" in w] == \
        [w for w in result["warnings"] if "Ghosted-ish" in w]


def test_csv_waits_on_the_server_between_map_and_import(client):
    import os
    page = client.post("/application/import", data={
        "csv_file": (io.BytesIO(b"Company,Role,Status\nAcme,Tester,Applied\n"), "jobs.csv"),
    }, content_type="multipart/form-data").get_data(as_text=True)
    assert 'name="csv_content"' not in page            # the file isn't sent back to the browser
    with client.session_transaction() as sess:
        stashed = sess["import_csv"]
    assert os.path.exists(stashed)
    page = client.post("/application/import", data={
        "stage": "import", "col_map_0": "company", "col_map_1": "job_desc", "col_map_2": "status",
    }).get_data(as_text=True)
    assert "1 added" in page
    assert _only_app()["status"] == "Submitted"
    assert not os.path.exists(stashed)                 # cleaned up after the import
    # A second Import click (or an expired upload) asks to upload again instead of failing.
    resp = client.post("/application/import", data={"stage": "import", "col_map_0": "company"})
    assert resp.status_code == 302


def test_import_adds_one_reminder_for_untagged_companies_not_one_each():
    db.bulk_import_applications([_row(company=f"New Co {i}") for i in range(12)])
    tags = [r for r in db.get_reminders(unread_only=True) if "industry tags" in r["message"]]
    assert len(tags) == 1 and tags[0]["message"].startswith("12 companies from your import")
    # Adding one by hand still gets its own reminder.
    db.add_application({"company": "Solo Co", "job_desc": "Role"})
    tags = [r for r in db.get_reminders(unread_only=True) if "industry tags" in r["message"]]
    assert len(tags) == 2

"""How-applied / employer-contact fields and the Workforce Australia report."""

import csv
import io
import re
from datetime import date

import pytest

import db
import routes.report as report


class _FixedDate(date):
    """date.today() pinned to Wednesday 28 October 2026."""
    @classmethod
    def today(cls):
        return cls(2026, 10, 28)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(report, "date", _FixedDate)
    db.set_setting("wfa_period_start", "")


def _add(company, applied, **extra):
    return db.add_application({"company": company, "job_desc": f"{company} role",
                               "date_applied": applied, **extra})


# ── Fields ───────────────────────────────────────────────────────────────────

def test_new_columns_exist():
    conn = db.get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(applications)")}
    conn.close()
    assert {"how_applied", "employer_contact"} <= cols


def test_form_saves_and_edits_the_new_fields(client):
    form = client.get("/application/add").get_data(as_text=True)
    assert 'name="how_applied"' in form and 'name="employer_contact"' in form
    client.post("/application/add", data={
        "company": "Acme", "job_desc": "Engineer", "date_applied": "2026-10-27",
        "how_applied": "Email", "employer_contact": "Jane Smith, jobs@acme.com.au",
    })
    app = db.get_applications(include_archived=True)[0]
    assert (app["how_applied"], app["employer_contact"]) == ("Email", "Jane Smith, jobs@acme.com.au")

    edit = client.get(f"/application/edit/{app['id']}").get_data(as_text=True)
    assert '<option value="Email" selected>' in edit
    client.post(f"/application/edit/{app['id']}", data={
        "company": "Acme", "job_desc": "Engineer", "date_applied": "2026-10-27",
        "status": app["status"], "how_applied": "In person", "employer_contact": "",
    })
    app = db.get_application(app["id"])
    assert (app["how_applied"], app["employer_contact"]) == ("In person", "")

    detail = client.get(f"/application/{app['id']}").get_data(as_text=True)
    assert "In person" in detail


def test_imported_free_text_how_applied_is_kept_on_the_form(client):
    app_id = _add("Acme", "2026-10-27", how_applied="LinkedIn Easy Apply")
    edit = client.get(f"/application/edit/{app_id}").get_data(as_text=True)
    assert '<option value="LinkedIn Easy Apply" selected>' in edit


def test_export_then_import_round_trips_the_new_fields(client):
    _add("Acme", "2026-10-27", how_applied="Email", employer_contact="Jane")
    exported = client.get("/export/applications").get_data(as_text=True)
    header = next(csv.reader(io.StringIO(exported)))
    assert "how_applied" in header and "employer_contact" in header

    # Edit the export and re-import it as an update.
    edited = exported.replace("Jane", "Jane Smith 0400 000 000")
    upload = client.post("/application/import", data={
        "csv_file": (io.BytesIO(edited.encode()), "apps.csv"), "header_row": "1",
    }, content_type="multipart/form-data")
    page = upload.get_data(as_text=True)
    import html as _html
    csv_content = _html.unescape(re.search(r'name="csv_content" value="([^"]*)"', page).group(1))
    # Column mapping guessed from the export headings.
    data = {"stage": "import", "csv_content": csv_content, "update_existing": "1"}
    for i, name in enumerate(header):
        data[f"col_map_{i}"] = name if name in ("id", "company", "job_desc", "date_applied",
                                                "how_applied", "employer_contact") else ""
        if name in ("how_applied", "employer_contact"):
            assert re.search(rf'name="col_map_{i}".*?value="{name}"\s+selected', page, re.S)
    client.post("/application/import", data=data)
    app = db.get_applications(include_archived=True)[0]
    assert (app["how_applied"], app["employer_contact"]) == ("Email", "Jane Smith 0400 000 000")


def test_import_update_without_the_columns_keeps_them():
    app_id = _add("Acme", "2026-10-27", how_applied="Email", employer_contact="Jane")
    db.bulk_import_applications([{"id": str(app_id), "status": "Submitted"}], update_existing=True)
    app = db.get_application(app_id)
    assert (app["status"], app["how_applied"], app["employer_contact"]) == ("Submitted", "Email", "Jane")


# ── Report period and rows ───────────────────────────────────────────────────

def test_applications_between_is_inclusive_and_per_user():
    _add("Before", "2026-10-18")
    _add("First", "2026-10-19")
    _add("Last", "2026-11-01T09:30:00")
    _add("After", "2026-11-02")
    db.add_application({"company": "Other user", "date_applied": "2026-10-20"}, user_id=99)
    mine = db.get_applications_applied_between("2026-10-19", "2026-11-01", user_id=None)
    assert [a["company"] for a in mine] == ["First", "Other user", "Last"]
    assert [a["company"] for a in db.get_applications_applied_between(
        "2026-10-19", "2026-11-01", user_id=99)] == ["Other user"]


def test_default_period_starts_this_monday(client):
    page = client.get("/report/workforce").get_data(as_text=True)
    assert "Mon 26 Oct – Sun 08 Nov 2026" in page
    assert "Showing fortnights from this Monday" in page


def test_saved_period_start_lines_up_fortnights(client):
    client.post("/report/workforce", data={"period_start": "2026-09-23"})
    assert db.get_setting("wfa_period_start") == "2026-09-23"
    page = client.get("/report/workforce").get_data(as_text=True)
    # 23 Sep + 14 + 14 = 21 Oct, which contains 28 Oct.
    assert "Wed 21 Oct – Tue 03 Nov 2026" in page
    assert "Current reporting period" in page
    assert "start=2026-10-07" in page and "start=2026-11-04" in page


def test_invalid_period_start_is_not_saved(client):
    client.post("/report/workforce", data={"period_start": "not a date"})
    assert db.get_setting("wfa_period_start") == ""


def test_report_lists_the_period_and_flags_missing_details(client):
    _add("Acme", "2026-10-27", how_applied="Email", employer_contact="Jane")
    archived = _add("Beta", "2026-10-28")
    db.archive_application(archived)
    _add("Older", "2026-10-01", how_applied="Email", employer_contact="Bob")
    page = client.get("/report/workforce?start=2026-10-26").get_data(as_text=True)
    assert "Acme" in page and "Beta" in page and "Older" not in page
    assert "27/10/2026" in page
    assert "<strong>2</strong> applications" in page
    assert "1 missing details" in page
    assert page.count("copy-row-btn") == 2
    assert "Back to current period" not in page


def test_report_csv(client):
    _add("Acme", "2026-10-27", how_applied="Email", employer_contact="Jane, 0400 000 000",
         status="Submitted")
    _add("Older", "2026-10-01")
    response = client.get("/report/workforce.csv?start=2026-10-26")
    assert response.mimetype == "text/csv"
    assert "workforce-report_2026-10-26_to_2026-11-08.csv" in response.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows == [
        ["Date applied", "Job title", "Employer", "How applied", "Employer contact", "Status", "Link"],
        ["27/10/2026", "Acme role", "Acme", "Email", "Jane, 0400 000 000", "Submitted", ""],
    ]


def test_empty_report(client):
    page = client.get("/report/workforce").get_data(as_text=True)
    assert "No applications with a date applied in this period" in page
    assert "js/workforce_report.js" in page

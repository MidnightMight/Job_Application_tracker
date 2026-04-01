import csv
import io
import os
import shutil

from flask import (
    Flask, flash, redirect, render_template,
    request, url_for, send_file, Response,
)
from apscheduler.schedulers.background import BackgroundScheduler

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "job-tracker-secret-key-change-me")

db.init_db()

app.jinja_env.globals["enumerate"] = enumerate


# ---------------------------------------------------------------------------
# Background scheduler — reminder checks
# ---------------------------------------------------------------------------

def _check_and_create_reminders():
    """Scheduled task: create inbox reminders for long-pending applications."""
    try:
        if db.get_setting("reminder_enabled", "1") != "1":
            return
        days = int(db.get_setting("reminder_days", "3"))
        for app_record in db.get_pending_for_reminders(days):
            msg = (
                f"'{app_record['job_desc'] or 'Application'}' at {app_record['company']} "
                f"has been pending ({app_record['status'].replace('_', ' ')}) "
                f"for {app_record['duration']} days."
            )
            db.create_reminder(app_record["id"], msg)
    except Exception:
        pass  # Never crash the scheduler thread


# Start scheduler only once (skip in Werkzeug reloader child process).
if os.environ.get("WERKZEUG_RUN_MAIN") != "false":
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_check_and_create_reminders, "interval", hours=1, id="reminders")
    _scheduler.start()
    # Also run once on startup so the inbox is populated immediately.
    _check_and_create_reminders()


@app.context_processor
def inject_globals():
    from datetime import date
    return {
        "years": db.YEARS,
        "current_year_for_footer": date.today().year,
        "unread_reminder_count": db.get_unread_reminder_count(),
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    current_year = 2025
    stats = db.get_stats(year=current_year)
    status_counts = db.get_status_counts(year=current_year)
    apps_per_year = db.get_apps_per_year()
    success_per_year = db.get_success_rate_per_year()
    keyword_freq = db.get_company_note_frequency()
    return render_template(
        "dashboard.html",
        stats=stats,
        status_counts=status_counts,
        apps_per_year=apps_per_year,
        success_per_year=success_per_year,
        keyword_freq=keyword_freq,
        current_year=current_year,
        years=db.YEARS,
    )


# ---------------------------------------------------------------------------
# Year view
# ---------------------------------------------------------------------------

@app.route("/year/<int:year>")
def year_view(year):
    status_filter = request.args.get("status", "")
    apps = db.get_applications(
        year=year,
        status=status_filter if status_filter else None,
    )
    stats = db.get_stats(year=year)
    return render_template(
        "year_view.html",
        apps=apps,
        year=year,
        stats=stats,
        years=db.YEARS,
        status_options=db.get_status_options(),
        selected_status=status_filter,
    )


# ---------------------------------------------------------------------------
# Application detail
# ---------------------------------------------------------------------------

@app.route("/application/<int:app_id>")
def application_detail(app_id):
    application = db.get_application(app_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard"))
    timeline = db.get_application_timeline(app_id)
    return render_template(
        "application_detail.html",
        app=application,
        timeline=timeline,
    )


# ---------------------------------------------------------------------------
# Add / edit / delete application
# ---------------------------------------------------------------------------

@app.route("/application/add", methods=["GET", "POST"])
def add_application():
    if request.method == "POST":
        db.add_application(request.form)
        flash("Application added.", "success")
        year = request.form.get("date_applied", "")[:4] or "2025"
        return redirect(url_for("year_view", year=year))
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=None,
        companies=companies_list,
        status_options=db.get_status_options(),
        action="Add",
    )


@app.route("/application/edit/<int:app_id>", methods=["GET", "POST"])
def edit_application(app_id):
    application = db.get_application(app_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        db.update_application(app_id, request.form)
        flash("Application updated.", "success")
        year = request.form.get("date_applied", "")[:4] or "2025"
        return redirect(url_for("year_view", year=year))
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=application,
        companies=companies_list,
        status_options=db.get_status_options(),
        action="Edit",
    )


@app.route("/application/delete/<int:app_id>", methods=["POST"])
def delete_application(app_id):
    application = db.get_application(app_id)
    year = application["date_applied"][:4] if application else "2025"
    db.delete_application(app_id)
    flash("Application deleted.", "warning")
    return redirect(url_for("year_view", year=year))


# ---------------------------------------------------------------------------
# CSV bulk import  (Mouser/DigiKey-style column mapping)
# ---------------------------------------------------------------------------

# Application fields that can be mapped from a CSV column.
CSV_IMPORT_FIELDS = [
    ("",                "(ignore this column)"),
    ("company",         "Company *"),
    ("date_applied",    "Date Applied *"),
    ("job_desc",        "Job Description / Role"),
    ("team",            "Team / Division"),
    ("status",          "Status"),
    ("cover_letter",    "Cover Letter (1/0)"),
    ("resume",          "Resume (1/0)"),
    ("success_chance",  "Success Chance"),
    ("link",            "Application Link"),
    ("contact",         "Known Contact / Connection"),
    ("comment",         "Comment / Notes"),
    ("additional_notes","Additional Notes"),
]


@app.route("/application/import", methods=["GET", "POST"])
def import_csv():
    """
    Step 1 (GET or first POST with a file): Upload CSV and show column-mapping UI.
    Step 2 (POST with mapping confirmed): Run the import and show results.
    """
    if request.method == "GET":
        return render_template("csv_import.html", stage="upload",
                               import_fields=CSV_IMPORT_FIELDS)

    # ── Step 1: file just uploaded — show column mapper ─────────────────────
    if "csv_file" in request.files and request.files["csv_file"].filename:
        file = request.files["csv_file"]
        try:
            content = file.read().decode("utf-8-sig")  # strip BOM if present
        except UnicodeDecodeError:
            content = file.read().decode("latin-1")

        reader = csv.reader(io.StringIO(content))
        headers = next(reader, [])
        if not headers:
            flash("The uploaded CSV has no header row.", "danger")
            return redirect(url_for("import_csv"))

        # Read up to 5 preview rows.
        preview_rows = []
        for i, row in enumerate(reader):
            if i >= 5:
                break
            preview_rows.append(row)

        # Auto-guess mappings: compare lowercased CSV headers to field keys.
        field_keys = {f[0]: f[1] for f in CSV_IMPORT_FIELDS if f[0]}
        guessed = []
        for h in headers:
            normalised = h.lower().replace(" ", "_").replace("-", "_")
            match = ""
            for key in field_keys:
                if key in normalised or normalised in key:
                    match = key
                    break
            guessed.append(match)

        return render_template(
            "csv_import.html",
            stage="map",
            headers=headers,
            preview_rows=preview_rows,
            guessed=guessed,
            csv_content=content,
            import_fields=CSV_IMPORT_FIELDS,
        )

    # ── Step 2: column mapping submitted — run import ────────────────────────
    if request.form.get("stage") == "import":
        content = request.form.get("csv_content", "")
        reader = csv.reader(io.StringIO(content))
        headers = next(reader, [])

        # Build index→field map from the form (col_map_0, col_map_1 …).
        col_map = {}
        for i in range(len(headers)):
            field = request.form.get(f"col_map_{i}", "")
            if field:
                col_map[i] = field

        rows_to_import = []
        for raw_row in reader:
            record = {}
            for idx, field in col_map.items():
                if idx < len(raw_row):
                    record[field] = raw_row[idx].strip()
            rows_to_import.append(record)

        result = db.bulk_import_applications(rows_to_import)
        flash(
            f"Import complete — {result['imported']} added, "
            f"{result['skipped']} skipped.",
            "success" if not result["errors"] else "warning",
        )
        return render_template(
            "csv_import.html",
            stage="result",
            result=result,
            import_fields=CSV_IMPORT_FIELDS,
        )

    flash("No file was uploaded.", "warning")
    return redirect(url_for("import_csv"))


# ---------------------------------------------------------------------------
# Status manager
# ---------------------------------------------------------------------------

@app.route("/statuses", methods=["GET", "POST"])
def manage_statuses():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            ok, msg = db.add_status(request.form.get("name", ""))
            flash(msg, "success" if ok else "danger")
        elif action == "delete":
            ok, msg = db.delete_status(request.form.get("name", ""))
            flash(msg, "success" if ok else "danger")
        return redirect(url_for("manage_statuses"))
    statuses = db.get_status_options()
    return render_template("status_manager.html", statuses=statuses)


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

@app.route("/companies")
def companies():
    companies_list = db.get_companies()
    sector_freq = db.get_company_note_frequency()
    return render_template(
        "companies.html",
        companies=companies_list,
        years=db.YEARS,
        sector_freq=sector_freq,
    )


@app.route("/company/add", methods=["GET", "POST"])
def add_company():
    if request.method == "POST":
        db.add_company(request.form)
        flash("Company added successfully.", "success")
        return redirect(url_for("companies"))
    return render_template(
        "company_form.html", company=None, years=db.YEARS, action="Add"
    )


@app.route("/company/edit/<int:company_id>", methods=["GET", "POST"])
def edit_company(company_id):
    company = db.get_company(company_id)
    if not company:
        flash("Company not found.", "danger")
        return redirect(url_for("companies"))
    if request.method == "POST":
        db.update_company(company_id, request.form)
        flash("Company updated.", "success")
        return redirect(url_for("companies"))
    return render_template(
        "company_form.html", company=company, years=db.YEARS, action="Edit"
    )


@app.route("/company/delete/<int:company_id>", methods=["POST"])
def delete_company(company_id):
    db.delete_company(company_id)
    flash("Company deleted.", "warning")
    return redirect(url_for("companies"))


# ---------------------------------------------------------------------------
# Inbox (reminders)
# ---------------------------------------------------------------------------

@app.route("/inbox")
def inbox():
    reminders = db.get_reminders()
    return render_template("inbox.html", reminders=reminders)


@app.route("/inbox/dismiss/<int:reminder_id>", methods=["POST"])
def dismiss_reminder(reminder_id):
    db.dismiss_reminder(reminder_id)
    return redirect(url_for("inbox"))


@app.route("/inbox/dismiss-all", methods=["POST"])
def dismiss_all_reminders():
    db.dismiss_all_reminders()
    flash("All reminders dismissed.", "success")
    return redirect(url_for("inbox"))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        db.set_setting("reminder_enabled", "1" if request.form.get("reminder_enabled") else "0")
        days = request.form.get("reminder_days", "3").strip()
        if days.isdigit() and int(days) >= 1:
            db.set_setting("reminder_days", days)
        else:
            flash("Reminder days must be a positive integer.", "danger")
            return redirect(url_for("settings"))
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))
    current = db.get_all_settings()
    return render_template("settings.html", settings=current)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.route("/export")
def export_page():
    status_options = db.get_status_options()
    return render_template(
        "export.html",
        years=db.YEARS,
        status_options=status_options,
    )


@app.route("/export/applications")
def export_applications():
    year = request.args.get("year", "")
    status = request.args.get("status", "")
    company = request.args.get("company", "").strip()

    apps = db.get_applications(
        year=int(year) if year.isdigit() else None,
        status=status if status else None,
    )
    if company:
        apps = [a for a in apps if company.lower() in a["company"].lower()]

    fields = [
        "id", "company", "job_desc", "team", "date_applied", "status",
        "cover_letter", "resume", "duration", "success_chance",
        "link", "contact", "comment", "additional_notes",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(apps)

    filename_parts = ["applications"]
    if year:
        filename_parts.append(year)
    if status:
        filename_parts.append(status)
    filename = "_".join(filename_parts) + ".csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/export/companies")
def export_companies():
    companies_list = db.get_companies()
    fields = ["id", "company_name", "note",
              "applied_2023", "applied_2024", "applied_2025",
              "applied_2026", "applied_2027"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(companies_list)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=companies.csv"},
    )


@app.route("/export/db")
def export_db():
    """Download a copy of the SQLite database for migration / backup."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(db.DB_PATH, tmp.name)
    return send_file(
        tmp.name,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name="jobs_backup.db",
    )


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

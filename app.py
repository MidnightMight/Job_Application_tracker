import base64
import csv
import io
import os
import shutil
from types import SimpleNamespace

from flask import (
    Flask, flash, redirect, render_template,
    request, url_for, send_file, Response,
)
from apscheduler.schedulers.background import BackgroundScheduler
import openpyxl

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
        company     = request.form.get("company", "").strip()
        job_desc    = request.form.get("job_desc", "").strip()
        date_applied = request.form.get("date_applied", "").strip()

        # Check for duplicates unless the user has explicitly confirmed.
        if request.form.get("force_add") != "1":
            duplicates = db.find_duplicate_applications(company, job_desc, date_applied)
            if duplicates:
                # Re-render the form with the submitted values preserved and
                # trigger the duplicate-warning modal.
                form_data = SimpleNamespace(
                    job_desc=job_desc,
                    company=company,
                    team=request.form.get("team", ""),
                    contact=request.form.get("contact", ""),
                    date_applied=date_applied,
                    status=request.form.get("status", "Select_Status"),
                    success_chance=request.form.get("success_chance", "0"),
                    link=request.form.get("link", ""),
                    cover_letter=1 if request.form.get("cover_letter") else 0,
                    resume=1 if request.form.get("resume") else 0,
                    comment=request.form.get("comment", ""),
                    additional_notes=request.form.get("additional_notes", ""),
                )
                return render_template(
                    "application_form.html",
                    app=form_data,
                    companies=db.get_companies(),
                    status_options=db.get_status_options(),
                    action="Add",
                    duplicate_warning=True,
                    duplicates=duplicates,
                )

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
# Bulk actions (multi-select in year view)
# ---------------------------------------------------------------------------

@app.route("/applications/bulk-action", methods=["POST"])
def bulk_action():
    """Handle bulk operations (delete / set-field) on multiple applications."""
    action      = request.form.get("action", "")
    year        = request.form.get("year",   "2025")
    status_filter = request.form.get("status_filter", "")

    raw_ids = request.form.getlist("selected_ids")
    try:
        selected_ids = [int(x) for x in raw_ids if str(x).isdigit()]
    except ValueError:
        selected_ids = []

    redirect_kwargs: dict = {"year": year}
    if status_filter:
        redirect_kwargs["status"] = status_filter

    if not selected_ids:
        flash("No applications selected.", "warning")
        return redirect(url_for("year_view", **redirect_kwargs))

    if action == "delete":
        count = db.bulk_delete_applications(selected_ids)
        flash(f"Deleted {count} application(s).", "warning")

    elif action == "set_status":
        new_status = request.form.get("bulk_status", "").strip()
        if not new_status:
            flash("Please choose a status.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "status", new_status)
            flash(
                f"Status set to '{new_status.replace('_', ' ')}' "
                f"for {count} application(s).",
                "success",
            )

    elif action == "set_date_applied":
        new_date = request.form.get("bulk_date_applied", "").strip()
        if not new_date:
            flash("Please enter a date.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "date_applied", new_date)
            flash(f"Date Applied set to {new_date} for {count} application(s).", "success")

    elif action == "set_last_contact":
        new_date = request.form.get("bulk_last_contact", "").strip()
        if not new_date:
            flash("Please enter a date.", "warning")
        else:
            count = db.bulk_update_applications(selected_ids, "last_contact_date", new_date)
            flash(f"Last Contact set to {new_date} for {count} application(s).", "success")

    elif action == "set_cover_letter":
        value = 1 if request.form.get("bulk_cover_letter") == "1" else 0
        label = "Yes" if value else "No"
        count = db.bulk_update_applications(selected_ids, "cover_letter", value)
        flash(f"Cover Letter set to {label} for {count} application(s).", "success")

    elif action == "set_resume":
        value = 1 if request.form.get("bulk_resume") == "1" else 0
        label = "Yes" if value else "No"
        count = db.bulk_update_applications(selected_ids, "resume", value)
        flash(f"Resume set to {label} for {count} application(s).", "success")

    else:
        flash("Unknown bulk action.", "warning")

    return redirect(url_for("year_view", **redirect_kwargs))


# ---------------------------------------------------------------------------
# CSV / Excel bulk import  (Mouser/DigiKey-style column mapping)
# ---------------------------------------------------------------------------

# Recognised Excel file extensions.
_EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}


def _excel_sheet_to_csv(workbook_bytes: bytes, sheet_name: str, start_row: int = 1) -> str:
    """Read one sheet from an Excel workbook and return it as a CSV string.

    ``start_row`` is 1-indexed; rows before it are skipped so the first row
    of the returned CSV is the header row chosen by the user.
    """
    wb = openpyxl.load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=True)
    ws = wb[sheet_name]
    out = io.StringIO()
    writer = csv.writer(out)
    for row in ws.iter_rows(min_row=max(1, start_row), values_only=True):
        writer.writerow([("" if cell is None else str(cell)) for cell in row])
    wb.close()
    return out.getvalue()


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
    Step 1  (GET or first POST with a file): Upload file.
              – CSV  → proceed straight to column mapping.
              – Excel → show sheet picker.
    Step 1b (POST with stage='sheet'): Excel sheet selected → convert to CSV
              and proceed to column mapping.
    Step 2  (POST with stage='import'): Run the import and show results.
    """
    if request.method == "GET":
        return render_template("csv_import.html", stage="upload",
                               import_fields=CSV_IMPORT_FIELDS)

    # ── Step 1b: sheet selected from an Excel file ───────────────────────────
    if request.form.get("stage") == "sheet":
        wb_b64 = request.form.get("wb_b64", "")
        sheet_name = request.form.get("sheet_name", "")
        filename = request.form.get("filename", "")
        try:
            header_row = max(1, int(request.form.get("header_row", "1") or "1"))
        except ValueError:
            header_row = 1
        if not wb_b64 or not sheet_name:
            flash("Sheet selection is missing. Please upload the file again.", "danger")
            return redirect(url_for("import_csv"))
        try:
            workbook_bytes = base64.b64decode(wb_b64)
            content = _excel_sheet_to_csv(workbook_bytes, sheet_name, start_row=header_row)
        except Exception as exc:
            flash(f"Could not read sheet '{sheet_name}': {exc}", "danger")
            return redirect(url_for("import_csv"))

        reader = csv.reader(io.StringIO(content))
        headers = next(reader, [])
        if not headers:
            flash("The selected sheet has no header row.", "danger")
            return redirect(url_for("import_csv"))

        preview_rows = [row for i, row in enumerate(reader) if i < 5]

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

        source_label = f"{filename} — {sheet_name}"
        if header_row > 1:
            source_label += f" (starting row {header_row})"
        return render_template(
            "csv_import.html",
            stage="map",
            headers=headers,
            preview_rows=preview_rows,
            guessed=guessed,
            csv_content=content,
            import_fields=CSV_IMPORT_FIELDS,
            source_label=source_label,
        )

    # ── Step 1: file just uploaded — detect type and show next step ──────────
    if "csv_file" in request.files and request.files["csv_file"].filename:
        file = request.files["csv_file"]
        filename = file.filename or ""
        ext = os.path.splitext(filename)[1].lower()
        raw_bytes = file.read()  # read once; file pointer is consumed after this

        # ── Excel path ───────────────────────────────────────────────────────
        if ext in _EXCEL_EXTENSIONS:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True)
                sheet_names = wb.sheetnames
                wb.close()
            except Exception as exc:
                flash(f"Could not open the Excel file: {exc}", "danger")
                return redirect(url_for("import_csv"))

            wb_b64 = base64.b64encode(raw_bytes).decode("ascii")
            return render_template(
                "csv_import.html",
                stage="sheet",
                sheet_names=sheet_names,
                wb_b64=wb_b64,
                filename=filename,
                import_fields=CSV_IMPORT_FIELDS,
            )

        # ── CSV path ─────────────────────────────────────────────────────────
        try:
            content = raw_bytes.decode("utf-8-sig")  # strip BOM if present
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1")

        try:
            header_row = max(1, int(request.form.get("header_row", "1") or "1"))
        except ValueError:
            header_row = 1

        reader = csv.reader(io.StringIO(content))
        # Skip rows before the chosen header row.
        for _ in range(header_row - 1):
            next(reader, None)
        headers = next(reader, [])
        if not headers:
            flash("The uploaded file has no header row at the specified row.", "danger")
            return redirect(url_for("import_csv"))

        # Rebuild csv_content starting from the header row so the import stage
        # can read it as a plain header + data CSV without further offsets.
        remaining_rows = list(reader)
        csv_buf = io.StringIO()
        csv_writer = csv.writer(csv_buf)
        csv_writer.writerow(headers)
        csv_writer.writerows(remaining_rows)
        content = csv_buf.getvalue()

        # Read up to 5 preview rows.
        preview_rows = remaining_rows[:5]

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

        source_label = filename
        if header_row > 1:
            source_label += f" (starting row {header_row})"
        return render_template(
            "csv_import.html",
            stage="map",
            headers=headers,
            preview_rows=preview_rows,
            guessed=guessed,
            csv_content=content,
            import_fields=CSV_IMPORT_FIELDS,
            source_label=source_label,
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
        dup_note = (
            f", {result['duplicates']} duplicate(s) skipped" if result["duplicates"] else ""
        )
        flash(
            f"Import complete — {result['imported']} added, "
            f"{result['skipped']} skipped{dup_note}.",
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

import csv
import io
import os

from flask import (
    Flask, flash, redirect, render_template,
    request, url_for,
)

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "job-tracker-secret-key-change-me")

db.init_db()

app.jinja_env.globals["enumerate"] = enumerate


@app.context_processor
def inject_globals():
    from datetime import date
    return {
        "years": db.YEARS,
        "current_year_for_footer": date.today().year,
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

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

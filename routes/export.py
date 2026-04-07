"""Export routes (CSV and DB download)."""

import csv
import io
import os
import shutil
import sqlite3
import tempfile

from flask import Blueprint, flash, redirect, render_template, request, Response, send_file, url_for

import db
from .auth import login_required

bp = Blueprint("export", __name__)


@bp.route("/export")
def export_page():
    status_options = db.get_status_options()
    return render_template(
        "export.html",
        years=db.get_dynamic_years(),
        status_options=status_options,
    )


@bp.route("/export/applications")
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
        "job_expiry_date", "industry", "last_modified_at",
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


@bp.route("/export/companies")
def export_companies():
    companies_list = db.get_companies()
    fields = [
        "id", "company_name", "note", "industry",
        "applied_2023", "applied_2024", "applied_2025",
        "applied_2026", "applied_2027",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(companies_list)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=companies.csv"},
    )


@bp.route("/export/db")
def export_db():
    """Download a copy of the SQLite database for migration / backup."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(db.DB_PATH, tmp.name)
    return send_file(
        tmp.name,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name="jobs_backup.db",
    )


@bp.route("/export/db/restore", methods=["POST"])
@login_required
def restore_db():
    """Replace the current database with an uploaded backup file."""
    uploaded = request.files.get("db_file")
    if not uploaded or uploaded.filename == "":
        flash("No file selected. Please choose a .db file to restore.", "danger")
        return redirect(url_for("export.export_page"))

    # Save the upload to a temp file for validation
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        uploaded.save(tmp.name)

        # Validate that the file is a SQLite database
        try:
            conn = sqlite3.connect(tmp.name)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError("integrity check failed")
        except sqlite3.DatabaseError:
            flash("The uploaded file does not appear to be a valid SQLite database.", "danger")
            return redirect(url_for("export.export_page"))

        # Back up the current database before overwriting
        backup_path = os.path.join(
            os.path.dirname(db.DB_PATH), os.path.basename(db.DB_PATH) + ".bak"
        )
        shutil.copy2(db.DB_PATH, backup_path)

        # Replace the current database
        shutil.copy2(tmp.name, db.DB_PATH)
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    flash("Database restored successfully. The previous database was saved as jobs.db.bak.", "success")
    return redirect(url_for("export.export_page"))

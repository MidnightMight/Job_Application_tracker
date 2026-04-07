"""Export routes (CSV and DB download)."""

import csv
import io
import shutil
import tempfile

from flask import Blueprint, render_template, request, Response, send_file

import db

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

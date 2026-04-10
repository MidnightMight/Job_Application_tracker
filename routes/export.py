"""Export routes (CSV and DB download)."""

import csv
import io
import logging
import os
import shutil
import sqlite3
import tempfile

from flask import Blueprint, flash, redirect, render_template, request, Response, send_file, url_for

import db
from .auth import login_required, current_user_id

bp = Blueprint("export", __name__)
logger = logging.getLogger(__name__)


@bp.route("/export")
@login_required
def export_page():
    user_id = current_user_id()
    status_options = db.get_status_options(user_id=user_id)
    return render_template(
        "export.html",
        years=db.get_dynamic_years(user_id=user_id),
        status_options=status_options,
    )


@bp.route("/export/applications")
@login_required
def export_applications():
    user_id = current_user_id()
    year = request.args.get("year", "")
    status = request.args.get("status", "")
    company = request.args.get("company", "").strip()

    apps = db.get_applications(
        year=int(year) if year.isdigit() else None,
        status=status if status else None,
        user_id=user_id,
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
    logger.info("DB export requested by %s", request.remote_addr)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(db.DB_PATH, tmp.name)
    logger.info("DB export: copied %s → %s (%.1f KB)", db.DB_PATH, tmp.name,
                os.path.getsize(tmp.name) / 1024)
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
    logger.info("DB restore requested by %s", request.remote_addr)

    uploaded = request.files.get("db_file")
    if not uploaded or uploaded.filename == "":
        logger.warning("DB restore: no file provided")
        flash("No file selected. Please choose a .db file to restore.", "danger")
        return redirect(url_for("export.export_page"))

    # Save the upload to a temp file for validation
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        uploaded.save(tmp.name)
        upload_size = os.path.getsize(tmp.name)
        logger.info("DB restore: upload saved to %s (%.1f KB)", tmp.name, upload_size / 1024)

        # Validate that the file is a SQLite database
        try:
            conn = sqlite3.connect(tmp.name)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            # Log schema from the uploaded DB for diagnostics
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            logger.info("DB restore: uploaded DB tables = %s", tables)
            for tbl in tables:
                # Only query tables whose names are safe SQL identifiers
                if tbl.replace("_", "").isalnum():
                    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                    logger.info("DB restore: table '%s' columns = %s", tbl, cols)
            conn.close()
            logger.info("DB restore: integrity_check result = %s", result[0] if result else "N/A")
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError("integrity check failed")
        except sqlite3.DatabaseError as exc:
            logger.error("DB restore: uploaded file is not a valid SQLite DB — %s", exc)
            flash("The uploaded file does not appear to be a valid SQLite database.", "danger")
            return redirect(url_for("export.export_page"))

        # Back up the current database before overwriting
        backup_path = os.path.join(
            os.path.dirname(db.DB_PATH), os.path.basename(db.DB_PATH) + ".bak"
        )
        shutil.copy2(db.DB_PATH, backup_path)
        logger.info("DB restore: current DB backed up to %s", backup_path)

        # Replace the current database
        shutil.copy2(tmp.name, db.DB_PATH)
        logger.info("DB restore: new DB written to %s", db.DB_PATH)

        # Log WAL/SHM files that may still be present
        for suffix in ("-wal", "-shm"):
            wal_path = db.DB_PATH + suffix
            if os.path.exists(wal_path):
                logger.warning("DB restore: stale WAL/SHM file found after copy: %s", wal_path)
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    # Run migrations so any columns added since the backup was taken are created.
    logger.info("DB restore: running init_db() to apply any missing migrations …")
    try:
        db.init_db()
        # Log final schema of applications table
        conn2 = sqlite3.connect(db.DB_PATH)
        cols = [r[1] for r in conn2.execute("PRAGMA table_info(applications)").fetchall()]
        conn2.close()
        logger.info("DB restore: applications columns after init_db = %s", cols)
    except Exception:
        logger.exception("DB restore: init_db() raised an exception")
        raise

    logger.info("DB restore: completed successfully")
    flash("Database restored successfully. The previous database was saved as jobs.db.bak.", "success")
    return redirect(url_for("export.export_page"))

import sqlite3
import os
from datetime import date, datetime

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "jobs.db"),
)

# Default statuses – used only to seed the statuses table on first run.
DEFAULT_STATUSES = [
    "Select_Status",
    "Drafting_CV",
    "Submitted",
    "Online_Assessment",
    "Awaiting_Response",
    "Interview_Scheduled",
    "Interview_In_Person",
    "Rejected",
    "Likely_Rejected",
    "Offer_Received",
    "Offer_Rejected",
    "Not_Applying",
    "EOI",
]

PENDING_STATUSES = {
    "Drafting_CV",
    "Submitted",
    "Online_Assessment",
    "Awaiting_Response",
    "Interview_Scheduled",
    "Interview_In_Person",
    "EOI",
}

YEARS = [2023, 2024, 2025, 2026, 2027]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_ALLOWED_TABLES  = {"applications", "companies", "status_history", "statuses", "reminders", "settings"}
_ALLOWED_COLUMNS = {
    "contact", "additional_notes", "status_changed_at", "last_contact_date",
}
_ALLOWED_DEFINITIONS = {"TEXT", "INTEGER DEFAULT 0"}

# Fields that may be updated via the bulk-action route.
_BULK_UPDATE_FIELDS = {"status", "cover_letter", "resume", "date_applied", "last_contact_date"}


def _add_column_if_missing(c, table: str, column: str, definition: str):
    """Safely add a column to an existing table (migration helper).

    All three parameters are validated against allowlists so that this
    internal helper can never be used as a SQL-injection vector.
    """
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"_add_column_if_missing: unknown table '{table}'")
    if column not in _ALLOWED_COLUMNS:
        raise ValueError(f"_add_column_if_missing: unknown column '{column}'")
    if definition not in _ALLOWED_DEFINITIONS:
        raise ValueError(f"_add_column_if_missing: unknown definition '{definition}'")
    # Safe to interpolate — values validated against allowlists above.
    existing = [row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in existing:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ── Applications ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            job_desc          TEXT,
            team              TEXT,
            company           TEXT,
            date_applied      TEXT,
            status            TEXT DEFAULT 'Select_Status',
            cover_letter      INTEGER DEFAULT 0,
            resume            INTEGER DEFAULT 1,
            comment           TEXT,
            success_chance    REAL DEFAULT 0,
            link              TEXT,
            contact           TEXT,
            additional_notes  TEXT,
            status_changed_at TEXT,
            last_contact_date TEXT
        )
    """)

    # Migrations for databases that existed before these columns were added.
    _add_column_if_missing(c, "applications", "contact",           "TEXT")
    _add_column_if_missing(c, "applications", "additional_notes",  "TEXT")
    _add_column_if_missing(c, "applications", "status_changed_at", "TEXT")
    _add_column_if_missing(c, "applications", "last_contact_date", "TEXT")

    # ── Status history ───────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            status         TEXT    NOT NULL,
            changed_at     TEXT    NOT NULL,
            FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
        )
    """)

    # ── Companies ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name  TEXT NOT NULL,
            note          TEXT,
            applied_2023  INTEGER DEFAULT 0,
            applied_2024  INTEGER DEFAULT 0,
            applied_2025  INTEGER DEFAULT 0,
            applied_2026  INTEGER DEFAULT 0,
            applied_2027  INTEGER DEFAULT 0
        )
    """)

    # ── Custom statuses ──────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    UNIQUE NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
    """)

    # ── Settings ─────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # ── Reminders (inbox) ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            message        TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            dismissed      INTEGER DEFAULT 0,
            FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
        )
    """)

    conn.commit()

    # Seed default settings if the table is empty.
    if c.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
        default_settings = [
            ("reminder_enabled", "1"),
            ("reminder_days",    "3"),
        ]
        c.executemany("INSERT INTO settings (key, value) VALUES (?,?)", default_settings)
        conn.commit()

    # Seed statuses if empty.
    if c.execute("SELECT COUNT(*) FROM statuses").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO statuses (name, sort_order) VALUES (?,?)",
            [(name, i) for i, name in enumerate(DEFAULT_STATUSES)],
        )
        conn.commit()

    # Migrate old status names to new normalised names in existing data.
    _migrate_legacy_status_names(c)
    conn.commit()

    # Seed sample data only if tables are empty.
    if c.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0:
        _seed_applications(c)
        conn.commit()

    if c.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0:
        _seed_companies(c)
        conn.commit()

    conn.close()


def _migrate_legacy_status_names(c):
    """Rename old inconsistently-capitalised status values to the new names."""
    renames = {
        "Offer_recieved":     "Offer_Received",
        "Offer_received":     "Offer_Received",
        "Offer_rejected":     "Offer_Rejected",
        "Interview_scheduled":"Interview_Scheduled",
        "Interview_inperson": "Interview_In_Person",
        "Online_assessment":  "Online_Assessment",
        "Awaiting_Response":  "Awaiting_Response",
        "Likely Rejected":    "Likely_Rejected",
        "Not Applying":       "Not_Applying",
    }
    for old, new in renames.items():
        c.execute(
            "UPDATE applications SET status=? WHERE status=?", (new, old)
        )
        c.execute(
            "UPDATE status_history SET status=? WHERE status=?", (new, old)
        )


# ---------------------------------------------------------------------------
# Status management
# ---------------------------------------------------------------------------

def get_status_options():
    conn = get_connection()
    rows = conn.execute(
        "SELECT name FROM statuses ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def add_status(name: str):
    name = name.strip().replace(" ", "_")
    if not name:
        return False, "Status name cannot be empty."
    conn = get_connection()
    try:
        max_order = conn.execute("SELECT MAX(sort_order) FROM statuses").fetchone()[0] or 0
        conn.execute(
            "INSERT INTO statuses (name, sort_order) VALUES (?,?)",
            (name, max_order + 1),
        )
        conn.commit()
        return True, f"Status '{name}' added."
    except sqlite3.IntegrityError:
        return False, f"Status '{name}' already exists."
    finally:
        conn.close()


def delete_status(name: str):
    """Delete a custom status. Prevents deletion if any application uses it."""
    conn = get_connection()
    in_use = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status=?", (name,)
    ).fetchone()[0]
    if in_use:
        conn.close()
        return False, f"Cannot delete '{name}' — {in_use} application(s) use it."
    conn.execute("DELETE FROM statuses WHERE name=?", (name,))
    conn.commit()
    conn.close()
    return True, f"Status '{name}' deleted."


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_applications(c):
    now = datetime.now().isoformat(timespec="seconds")
    example_apps = [
        # (job_desc, team, company, date_applied, status, cover_letter, resume,
        #  comment, success_chance, link, contact, additional_notes, status_changed_at)
        (
            "Graduate Engineer", "Electrical Team", "Acme Engineering",
            "2025-03-10", "Submitted", 1, 1,
            "Applied via company portal", 0.3,
            "https://example.com/jobs/1", "", "", now,
        ),
        (
            "Graduate Engineer", "Infrastructure", "Beta Consulting",
            "2025-03-15", "Interview_Scheduled", 1, 1,
            "Phone screen passed, technical interview on 2025-03-28", 0.5,
            "", "Jane Smith (recruiter)", "", now,
        ),
        (
            "Internship", "Research & Development", "Gamma Industries",
            "2024-07-20", "Offer_Received", 1, 1,
            "Verbal offer received, awaiting written contract", 0.9,
            "", "", "", now,
        ),
        (
            "Internship", "Civil Projects", "Delta Constructions",
            "2024-08-01", "Rejected", 1, 1,
            "", 0, "", "", "", now,
        ),
        (
            "Graduate Engineer", "", "Epsilon Energy",
            "2025-02-14", "Not_Applying", 0, 1,
            "Position requires 2+ years experience", 0,
            "https://example.com/jobs/5", "", "", now,
        ),
    ]

    sql = """INSERT INTO applications
             (job_desc, team, company, date_applied, status,
              cover_letter, resume, comment, success_chance, link,
              contact, additional_notes, status_changed_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    c.executemany(sql, example_apps)

    # Seed initial status history entries.
    for row in c.execute("SELECT id, status, date_applied FROM applications").fetchall():
        applied_dt = row["date_applied"] + "T00:00:00"
        c.execute(
            "INSERT INTO status_history (application_id, status, changed_at) VALUES (?,?,?)",
            (row["id"], row["status"], applied_dt),
        )


def _seed_companies(c):
    example_companies = [
        ("Acme Engineering",    "Engineering Consulting", 0, 0, 1, 0, 0),
        ("Beta Consulting",     "Management Consulting",  0, 0, 1, 0, 0),
        ("Gamma Industries",    "Manufacturing",          0, 1, 0, 0, 0),
        ("Delta Constructions", "Civil Construction",     0, 1, 0, 0, 0),
        ("Epsilon Energy",      "Energy Provider",        0, 0, 1, 0, 0),
    ]
    c.executemany(
        """INSERT INTO companies
           (company_name, note, applied_2023, applied_2024,
            applied_2025, applied_2026, applied_2027)
           VALUES (?,?,?,?,?,?,?)""",
        example_companies,
    )


# ---------------------------------------------------------------------------
# Application CRUD
# ---------------------------------------------------------------------------

def get_applications(year=None, status=None):
    conn = get_connection()
    sql = "SELECT * FROM applications WHERE 1=1"
    params = []
    if year:
        sql += " AND strftime('%Y', date_applied) = ?"
        params.append(str(year))
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date_applied DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_enrich(dict(r)) for r in rows]


def get_application(app_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM applications WHERE id=?", (app_id,)
    ).fetchone()
    conn.close()
    return _enrich(dict(row)) if row else None


def get_application_timeline(app_id):
    """Return status history entries for a single application, oldest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, changed_at FROM status_history "
        "WHERE application_id=? ORDER BY changed_at ASC",
        (app_id,),
    ).fetchall()
    conn.close()
    history = [dict(r) for r in rows]
    # Compute days between consecutive entries.
    for i, entry in enumerate(history):
        if i == 0:
            entry["days_since_prev"] = None
        else:
            try:
                prev = datetime.fromisoformat(history[i - 1]["changed_at"])
                curr = datetime.fromisoformat(entry["changed_at"])
                entry["days_since_prev"] = (curr - prev).days
            except Exception:
                entry["days_since_prev"] = None
    return history


def _enrich(app):
    """Add computed 'duration' field (days since applied)."""
    try:
        d = datetime.strptime(app["date_applied"], "%Y-%m-%d").date()
        app["duration"] = (date.today() - d).days
    except Exception:
        app["duration"] = 0
    return app


def add_application(data):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO applications
           (job_desc, team, company, date_applied, status,
            cover_letter, resume, comment, success_chance, link,
            contact, additional_notes, status_changed_at, last_contact_date)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data.get("job_desc", ""),
            data.get("team", ""),
            data.get("company", ""),
            data.get("date_applied", ""),
            data.get("status", "Select_Status"),
            1 if data.get("cover_letter") else 0,
            1 if data.get("resume") else 0,
            data.get("comment", ""),
            float(data.get("success_chance", 0) or 0),
            data.get("link", ""),
            data.get("contact", ""),
            data.get("additional_notes", ""),
            now,
            data.get("last_contact_date") or None,
        ),
    )
    app_id = cur.lastrowid
    conn.execute(
        "INSERT INTO status_history (application_id, status, changed_at) VALUES (?,?,?)",
        (app_id, data.get("status", "Select_Status"), now),
    )
    conn.commit()
    conn.close()
    return app_id


def update_application(app_id, data):
    now = datetime.now().isoformat(timespec="seconds")
    existing = get_application(app_id)
    new_status = data.get("status", "Select_Status")
    conn = get_connection()
    conn.execute(
        """UPDATE applications SET
           job_desc=?, team=?, company=?, date_applied=?, status=?,
           cover_letter=?, resume=?, comment=?, success_chance=?, link=?,
           contact=?, additional_notes=?, last_contact_date=?,
           status_changed_at=CASE WHEN status != ? THEN ? ELSE status_changed_at END
           WHERE id=?""",
        (
            data.get("job_desc", ""),
            data.get("team", ""),
            data.get("company", ""),
            data.get("date_applied", ""),
            new_status,
            1 if data.get("cover_letter") else 0,
            1 if data.get("resume") else 0,
            data.get("comment", ""),
            float(data.get("success_chance", 0) or 0),
            data.get("link", ""),
            data.get("contact", ""),
            data.get("additional_notes", ""),
            data.get("last_contact_date") or None,
            new_status,
            now,
            app_id,
        ),
    )
    # Record status change in history only when the status actually changes.
    if existing and existing.get("status") != new_status:
        conn.execute(
            "INSERT INTO status_history (application_id, status, changed_at) VALUES (?,?,?)",
            (app_id, new_status, now),
        )
    conn.commit()
    conn.close()


def delete_application(app_id):
    conn = get_connection()
    conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
    conn.commit()
    conn.close()


def bulk_delete_applications(ids: list) -> int:
    """Delete multiple applications by ID. Returns the number of rows deleted."""
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    conn = get_connection()
    conn.execute(f"DELETE FROM applications WHERE id IN ({placeholders})", ids)
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return count


def bulk_update_applications(ids: list, field: str, value) -> int:
    """
    Set ``field`` to ``value`` for all application IDs in ``ids``.

    Allowed fields: status, cover_letter, resume, date_applied, last_contact_date.
    For status updates this also records a status_history entry for each
    application whose status actually changes.
    Returns the number of rows updated.
    """
    if not ids:
        return 0
    if field not in _BULK_UPDATE_FIELDS:
        raise ValueError(f"bulk_update_applications: unknown field '{field}'")

    placeholders = ",".join("?" for _ in ids)
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()

    if field == "status":
        # Capture current statuses so we only record history for real changes.
        existing = {
            r["id"]: r["status"]
            for r in conn.execute(
                f"SELECT id, status FROM applications WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        }
        conn.execute(
            f"UPDATE applications SET status=?, status_changed_at=? "
            f"WHERE id IN ({placeholders})",
            (value, now, *ids),
        )
        for app_id in ids:
            if existing.get(app_id) != value:
                conn.execute(
                    "INSERT INTO status_history (application_id, status, changed_at) "
                    "VALUES (?,?,?)",
                    (app_id, value, now),
                )
    else:
        conn.execute(
            f"UPDATE applications SET {field}=? WHERE id IN ({placeholders})",
            (value, *ids),
        )

    # Count how many rows matched (changes() only reflects the last statement).
    count = conn.execute(
        f"SELECT COUNT(*) FROM applications WHERE id IN ({placeholders})", ids
    ).fetchone()[0]
    conn.commit()
    conn.close()
    return count


def _dup_key(company: str, job_desc: str, date_applied: str) -> tuple:
    """Return a normalised key used to identify duplicate applications."""
    return (company.strip().lower(), job_desc.strip().lower(), date_applied)


def find_duplicate_applications(company: str, job_desc: str, date_applied: str) -> list[dict]:
    """Return existing applications that match company, job_desc, and date_applied.

    Comparison is case-insensitive and ignores leading/trailing whitespace.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, company, job_desc, date_applied, status
           FROM applications
           WHERE LOWER(TRIM(company))     = ?
             AND LOWER(TRIM(job_desc))    = ?
             AND date_applied             = ?""",
        _dup_key(company, job_desc, date_applied),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CSV bulk import
# ---------------------------------------------------------------------------

def bulk_import_applications(rows: list[dict]) -> dict:
    """
    Import a list of dicts representing applications.
    Returns {"imported": int, "skipped": int, "duplicates": int,
             "other_skipped": int, "errors": list[str]}.
    Rows that are exact duplicates of existing records are skipped automatically.
    """
    # Pre-fetch all existing (company, job_desc, date_applied) keys in one query
    # to avoid an N+1 query pattern during the loop.
    conn = get_connection()
    existing_rows = conn.execute(
        "SELECT LOWER(TRIM(company)), LOWER(TRIM(job_desc)), date_applied FROM applications"
    ).fetchall()
    conn.close()
    existing_keys = {(r[0], r[1], r[2]) for r in existing_rows}

    imported = 0
    duplicates = 0
    errors = []
    for i, row in enumerate(rows, start=1):
        company = (row.get("company") or "").strip()
        if not company:
            errors.append(f"Row {i}: 'company' is required — row skipped.")
            continue
        date_applied = (row.get("date_applied") or "").strip()
        if not date_applied:
            errors.append(f"Row {i} ({company}): 'date_applied' is required — row skipped.")
            continue
        # Normalise date to YYYY-MM-DD if possible.
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                date_applied = datetime.strptime(date_applied, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass
        job_desc = (row.get("job_desc") or "").strip()
        lookup_key = _dup_key(company, job_desc, date_applied)
        if lookup_key in existing_keys:
            errors.append(
                f"Row {i} ({company}): duplicate application already in database — row skipped."
            )
            duplicates += 1
            continue
        add_application({
            "job_desc":        job_desc,
            "team":            row.get("team", ""),
            "company":         company,
            "date_applied":    date_applied,
            "status":          row.get("status", "Select_Status"),
            "cover_letter":    row.get("cover_letter", ""),
            "resume":          row.get("resume", "1"),
            "comment":         row.get("comment", ""),
            "success_chance":  row.get("success_chance", "0"),
            "link":            row.get("link", ""),
            "contact":         row.get("contact", ""),
            "additional_notes":row.get("additional_notes", ""),
        })
        # Track the newly added row so subsequent rows in the same import
        # are also treated as duplicates if they match.
        existing_keys.add(lookup_key)
        imported += 1
    total_skipped = len(rows) - imported
    return {
        "imported":      imported,
        "skipped":       total_skipped,
        "duplicates":    duplicates,
        "other_skipped": total_skipped - duplicates,
        "errors":        errors,
    }


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def get_companies():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM companies ORDER BY company_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company(company_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM companies WHERE id=?", (company_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_company(data):
    conn = get_connection()
    conn.execute(
        """INSERT INTO companies
           (company_name, note, applied_2023, applied_2024,
            applied_2025, applied_2026, applied_2027)
           VALUES (?,?,?,?,?,?,?)""",
        (
            data.get("company_name", ""),
            data.get("note", ""),
            1 if data.get("applied_2023") else 0,
            1 if data.get("applied_2024") else 0,
            1 if data.get("applied_2025") else 0,
            1 if data.get("applied_2026") else 0,
            1 if data.get("applied_2027") else 0,
        ),
    )
    conn.commit()
    conn.close()


def update_company(company_id, data):
    conn = get_connection()
    conn.execute(
        """UPDATE companies SET
           company_name=?, note=?,
           applied_2023=?, applied_2024=?, applied_2025=?,
           applied_2026=?, applied_2027=?
           WHERE id=?""",
        (
            data.get("company_name", ""),
            data.get("note", ""),
            1 if data.get("applied_2023") else 0,
            1 if data.get("applied_2024") else 0,
            1 if data.get("applied_2025") else 0,
            1 if data.get("applied_2026") else 0,
            1 if data.get("applied_2027") else 0,
            company_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_company(company_id):
    conn = get_connection()
    conn.execute("DELETE FROM companies WHERE id=?", (company_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def get_stats(year=None):
    apps = get_applications(year=year)
    total = len(apps)
    submitted = sum(
        1 for a in apps
        if a["status"] not in ("Select_Status", "Drafting_CV", "Not_Applying")
    )
    rejected = sum(1 for a in apps if "Rejected" in a["status"])
    offers = sum(1 for a in apps if a["status"] == "Offer_Received")
    success_rate = round((offers / submitted * 100), 1) if submitted else 0
    pending = [a for a in apps if a["status"] in PENDING_STATUSES]
    return {
        "total":        total,
        "submitted":    submitted,
        "rejected":     rejected,
        "offers":       offers,
        "success_rate": success_rate,
        "pending":      pending,
    }


def get_status_counts(year=None):
    apps = get_applications(year=year)
    counts: dict = {}
    for a in apps:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return counts


def get_apps_per_year():
    conn = get_connection()
    rows = conn.execute(
        """SELECT strftime('%Y', date_applied) as yr, COUNT(*) as cnt
           FROM applications GROUP BY yr ORDER BY yr"""
    ).fetchall()
    conn.close()
    result = {str(y): 0 for y in YEARS}
    for r in rows:
        if r["yr"] in result:
            result[r["yr"]] = r["cnt"]
    return result


def get_success_rate_per_year():
    result = {}
    for y in YEARS:
        apps = get_applications(year=y)
        submitted = sum(
            1 for a in apps
            if a["status"] not in ("Select_Status", "Drafting_CV", "Not_Applying")
        )
        offers = sum(1 for a in apps if a["status"] == "Offer_Received")
        result[str(y)] = round((offers / submitted * 100), 1) if submitted else 0
    return result


def get_company_note_frequency():
    """Return top sectors/notes from the companies table."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT note FROM companies WHERE note IS NOT NULL AND note != ''"
    ).fetchall()
    conn.close()
    freq: dict = {}
    for r in rows:
        note = r["note"].strip()
        if note:
            freq[note] = freq.get(note, 0) + 1
    return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15])


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def get_all_settings() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Reminders / inbox helpers
# ---------------------------------------------------------------------------

def get_pending_for_reminders(days_threshold: int) -> list:
    """Return pending applications that have been waiting more than days_threshold days
    and don't already have an undismissed reminder created within the last day."""
    conn = get_connection()
    placeholders = ",".join("?" for _ in PENDING_STATUSES)
    rows = conn.execute(
        f"""SELECT a.* FROM applications a
            WHERE a.status IN ({placeholders})
              AND julianday('now') - julianday(a.date_applied) > ?
              AND NOT EXISTS (
                  SELECT 1 FROM reminders r
                  WHERE r.application_id = a.id
                    AND r.dismissed = 0
                    AND julianday('now') - julianday(r.created_at) < 1
              )
        """,
        (*PENDING_STATUSES, days_threshold),
    ).fetchall()
    conn.close()
    return [_enrich(dict(r)) for r in rows]


def create_reminder(application_id: int, message: str):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "INSERT INTO reminders (application_id, message, created_at, dismissed) VALUES (?,?,?,0)",
        (application_id, message, now),
    )
    conn.commit()
    conn.close()


def get_reminders(unread_only: bool = False) -> list:
    conn = get_connection()
    sql = (
        "SELECT r.*, a.company, a.job_desc, a.status, a.date_applied "
        "FROM reminders r "
        "LEFT JOIN applications a ON a.id = r.application_id "
    )
    if unread_only:
        sql += "WHERE r.dismissed=0 "
    sql += "ORDER BY r.created_at DESC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_reminder(reminder_id: int):
    conn = get_connection()
    conn.execute("UPDATE reminders SET dismissed=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def dismiss_all_reminders():
    conn = get_connection()
    conn.execute("UPDATE reminders SET dismissed=1")
    conn.commit()
    conn.close()


def get_unread_reminder_count() -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE dismissed=0"
    ).fetchone()[0]
    conn.close()
    return count

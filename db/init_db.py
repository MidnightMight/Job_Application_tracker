"""Database initialisation, migrations, and seed data."""

from datetime import datetime

from .connection import get_connection, _add_column_if_missing

# Default statuses — used only to seed the statuses table on first run.
DEFAULT_STATUSES = [
    "Select_Status",
    "Drafting_Application",
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
    "Job_Expired",
    "EOI",
]

PENDING_STATUSES = {
    "Drafting_Application",
    "Drafting_CV",
    "Submitted",
    "Online_Assessment",
    "Awaiting_Response",
    "Interview_Scheduled",
    "Interview_In_Person",
    "EOI",
}


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
            last_contact_date TEXT,
            ai_fit_score      INTEGER,
            ai_fit_verdict    TEXT,
            ai_matching_skills TEXT,
            ai_skill_gaps     TEXT,
            ai_recommendation TEXT,
            last_modified_at  TEXT,
            job_expiry_date   TEXT,
            industry          TEXT,
            user_id           INTEGER,
            archived          INTEGER DEFAULT 0,
            archived_at       TEXT
        )
    """)

    # Migrations for databases that existed before these columns were added.
    _add_column_if_missing(c, "applications", "contact",             "TEXT")
    _add_column_if_missing(c, "applications", "additional_notes",    "TEXT")
    _add_column_if_missing(c, "applications", "status_changed_at",   "TEXT")
    _add_column_if_missing(c, "applications", "last_contact_date",   "TEXT")
    _add_column_if_missing(c, "applications", "ai_fit_score",        "INTEGER")
    _add_column_if_missing(c, "applications", "ai_fit_verdict",      "TEXT")
    _add_column_if_missing(c, "applications", "ai_matching_skills",  "TEXT")
    _add_column_if_missing(c, "applications", "ai_skill_gaps",       "TEXT")
    _add_column_if_missing(c, "applications", "ai_recommendation",   "TEXT")
    _add_column_if_missing(c, "applications", "last_modified_at",    "TEXT")
    _add_column_if_missing(c, "applications", "job_expiry_date",     "TEXT")
    _add_column_if_missing(c, "applications", "industry",            "TEXT")
    _add_column_if_missing(c, "applications", "user_id",             "INTEGER")
    _add_column_if_missing(c, "applications", "archived",            "INTEGER DEFAULT 0")
    _add_column_if_missing(c, "applications", "archived_at",         "TEXT")

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
            applied_2027  INTEGER DEFAULT 0,
            user_id       INTEGER,
            industry      TEXT
        )
    """)
    _col_names = [r[1] for r in c.execute("PRAGMA table_info(companies)").fetchall()]
    if "user_id" not in _col_names:
        c.execute("ALTER TABLE companies ADD COLUMN user_id INTEGER")
    if "industry" not in _col_names:
        c.execute("ALTER TABLE companies ADD COLUMN industry TEXT")

    # ── Custom statuses ──────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            sort_order INTEGER DEFAULT 0,
            bg_color   TEXT,
            text_color TEXT,
            user_id    INTEGER,
            UNIQUE(name, user_id)
        )
    """)
    _add_column_if_missing(c, "statuses", "bg_color",   "TEXT")
    _add_column_if_missing(c, "statuses", "text_color", "TEXT")
    _add_column_if_missing(c, "statuses", "user_id",    "INTEGER")

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
            reminder_type  TEXT,
            FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
        )
    """)
    _add_column_if_missing(c, "reminders", "reminder_type", "TEXT")

    # ── Users ─────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            username            TEXT UNIQUE NOT NULL,
            password_hash       TEXT NOT NULL DEFAULT '',
            is_admin            INTEGER DEFAULT 0,
            created_at          TEXT NOT NULL,
            needs_password_setup INTEGER DEFAULT 0,
            last_login_at       TEXT
        )
    """)
    _add_column_if_missing(c, "users", "needs_password_setup", "INTEGER DEFAULT 0")
    _add_column_if_missing(c, "users", "last_login_at", "TEXT")

    # ── Per-user AI settings ───────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_ai_settings (
            user_id             INTEGER PRIMARY KEY,
            ai_provider         TEXT NOT NULL DEFAULT 'ollama',
            api_key             TEXT NOT NULL DEFAULT '',
            api_url             TEXT NOT NULL DEFAULT '',
            ai_model            TEXT NOT NULL DEFAULT '',
            profile_skills      TEXT NOT NULL DEFAULT '',
            profile_experience  TEXT NOT NULL DEFAULT '',
            profile_summary     TEXT NOT NULL DEFAULT '',
            use_admin_ai        INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    _add_column_if_missing(c, "user_ai_settings", "use_admin_ai", "INTEGER DEFAULT 0")

    conn.commit()

    # Seed default settings if the table is empty.
    if c.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
        default_settings = [
            ("reminder_enabled",        "1"),
            ("reminder_days",           "3"),
            ("login_enabled",           "0"),
            ("ollama_enabled",          "0"),
            ("ollama_url",              "http://localhost:11434"),
            ("ollama_model",            "llama3"),
            ("company_pool_enabled",    "0"),
            ("ai_fit_enabled",          "0"),
            ("user_profile_skills",     ""),
            ("user_profile_experience", ""),
            ("user_profile_summary",    ""),
            ("onboarding_complete",     "0"),
            ("stale_threshold_value",   "2"),
            ("stale_threshold_unit",    "weeks"),
            ("rejected_threshold_value", "4"),
            ("rejected_threshold_unit", "weeks"),
            ("check_interval",          "1h"),
        ]
        c.executemany("INSERT INTO settings (key, value) VALUES (?,?)", default_settings)
        conn.commit()
    else:
        existing_keys = {r[0] for r in c.execute("SELECT key FROM settings").fetchall()}
        migrations = [
            ("login_enabled",           "0"),
            ("ollama_enabled",          "0"),
            ("ollama_url",              "http://localhost:11434"),
            ("ollama_model",            "llama3"),
            ("company_pool_enabled",    "0"),
            ("ai_fit_enabled",          "0"),
            ("user_profile_skills",     ""),
            ("user_profile_experience", ""),
            ("user_profile_summary",    ""),
            ("onboarding_complete",     "1"),
            ("stale_threshold_value",   "2"),
            ("stale_threshold_unit",    "weeks"),
            ("rejected_threshold_value", "4"),
            ("rejected_threshold_unit", "weeks"),
            ("check_interval",          "1h"),
        ]
        for key, value in migrations:
            if key not in existing_keys:
                c.execute("INSERT INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()

    # Seed statuses if empty.
    if c.execute("SELECT COUNT(*) FROM statuses").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO statuses (name, sort_order) VALUES (?,?)",
            [(name, i) for i, name in enumerate(DEFAULT_STATUSES)],
        )
        conn.commit()
    else:
        existing_statuses = {r[0] for r in c.execute("SELECT name FROM statuses").fetchall()}
        max_order = c.execute("SELECT COALESCE(MAX(sort_order), 0) FROM statuses").fetchone()[0]
        for name in ("Drafting_Application", "Job_Expired"):
            if name not in existing_statuses:
                max_order += 1
                c.execute(
                    "INSERT OR IGNORE INTO statuses (name, sort_order) VALUES (?,?)",
                    (name, max_order),
                )
        conn.commit()

    _migrate_legacy_status_names(c)
    conn.commit()

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
        "Offer_recieved":      "Offer_Received",
        "Offer_received":      "Offer_Received",
        "Offer_rejected":      "Offer_Rejected",
        "Interview_scheduled": "Interview_Scheduled",
        "Interview_inperson":  "Interview_In_Person",
        "Online_assessment":   "Online_Assessment",
        "Awaiting_Response":   "Awaiting_Response",
        "Likely Rejected":     "Likely_Rejected",
        "Not Applying":        "Not_Applying",
    }
    for old, new in renames.items():
        c.execute("UPDATE applications SET status=? WHERE status=?", (new, old))
        c.execute("UPDATE status_history SET status=? WHERE status=?", (new, old))


def clear_demo_data():
    """Delete all seeded sample applications, companies, and their history."""
    conn = get_connection()
    conn.execute("DELETE FROM status_history")
    conn.execute("DELETE FROM applications")
    conn.execute("DELETE FROM companies")
    conn.execute("DELETE FROM reminders")
    conn.commit()
    conn.close()


def _seed_applications(c):
    now = datetime.now().isoformat(timespec="seconds")
    example_apps = [
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

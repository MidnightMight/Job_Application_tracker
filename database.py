import sqlite3
import os
from datetime import date, datetime

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "jobs.db"),
)

STATUS_OPTIONS = [
    "Select_Status", "Drafting_CV", "Submitted", "Online_assessment",
    "Awaiting_Response", "Interview_scheduled", "Interview_inperson",
    "Rejected", "Likely Rejected", "Offer_recieved", "Offer_rejected",
    "Not Applying", "EOI",
]

PENDING_STATUSES = {
    "Drafting_CV", "Submitted", "Online_assessment",
    "Awaiting_Response", "Interview_scheduled", "Interview_inperson", "EOI",
}

YEARS = [2023, 2024, 2025, 2026, 2027]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_desc TEXT,
            team TEXT,
            company TEXT,
            date_applied TEXT,
            status TEXT DEFAULT 'Select_Status',
            cover_letter INTEGER DEFAULT 0,
            resume INTEGER DEFAULT 1,
            comment TEXT,
            success_chance REAL DEFAULT 0,
            link TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            note TEXT,
            applied_2023 INTEGER DEFAULT 0,
            applied_2024 INTEGER DEFAULT 0,
            applied_2025 INTEGER DEFAULT 0,
            applied_2026 INTEGER DEFAULT 0,
            applied_2027 INTEGER DEFAULT 0
        )
    """)

    conn.commit()

    # Seed only if tables are empty
    row = c.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    if row == 0:
        _seed_applications(c)
        conn.commit()

    row = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    if row == 0:
        _seed_companies(c)
        conn.commit()

    conn.close()


def _seed_applications(c):
    # Example applications demonstrating each key status.
    # Replace or delete these rows and add your own real applications.
    example_apps = [
        # (job_desc, team, company, date_applied, status, cover_letter, resume, comment, success_chance, link)
        ("Graduate Engineer", "Electrical Team", "Acme Engineering", "2025-03-10", "Submitted", 1, 1, "Applied via company portal", 0.3, "https://example.com/jobs/1"),
        ("Graduate Engineer", "Infrastructure", "Beta Consulting", "2025-03-15", "Interview_scheduled", 1, 1, "Phone screen passed, technical interview on 2025-03-28", 0.5, ""),
        ("Internship", "Research & Development", "Gamma Industries", "2024-07-20", "Offer_recieved", 1, 1, "Verbal offer received, awaiting written contract", 0.9, ""),
        ("Internship", "Civil Projects", "Delta Constructions", "2024-08-01", "Rejected", 1, 1, "", 0, ""),
        ("Graduate Engineer", "", "Epsilon Energy", "2025-02-14", "Not Applying", 0, 1, "Position requires 2+ years experience", 0, "https://example.com/jobs/5"),
    ]

    sql = """INSERT INTO applications
             (job_desc, team, company, date_applied, status,
               cover_letter, resume, comment, success_chance, link)
             VALUES (?,?,?,?,?,?,?,?,?,?)"""

    c.executemany(sql, example_apps)


def _seed_companies(c):
    # Example companies covering different sectors.
    # Replace or delete these rows and add your own companies.
    example_companies = [
        # (company_name, note, applied_2023, applied_2024, applied_2025, applied_2026, applied_2027)
        ("Acme Engineering", "Engineering Consulting", 0, 0, 1, 0, 0),
        ("Beta Consulting", "Management Consulting", 0, 0, 1, 0, 0),
        ("Gamma Industries", "Manufacturing", 0, 1, 0, 0, 0),
        ("Delta Constructions", "Civil Construction", 0, 1, 0, 0, 0),
        ("Epsilon Energy", "Energy Provider", 0, 0, 1, 0, 0),
    ]

    c.executemany(
        """INSERT INTO companies
           (company_name, note, applied_2023, applied_2024,
            applied_2025, applied_2026, applied_2027)
           VALUES (?,?,?,?,?,?,?)""",
        example_companies,
    )

# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_applications(year=None, status=None):
    conn = get_connection()
    c = conn.cursor()
    sql = "SELECT * FROM applications WHERE 1=1"
    params = []
    if year:
        sql += " AND strftime('%Y', date_applied) = ?"
        params.append(str(year))
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date_applied DESC"
    rows = c.execute(sql, params).fetchall()
    conn.close()
    return [_enrich(dict(r)) for r in rows]


def get_application(app_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    conn.close()
    return _enrich(dict(row)) if row else None


def _enrich(app):
    """Add computed 'duration' field."""
    try:
        d = datetime.strptime(app["date_applied"], "%Y-%m-%d").date()
        app["duration"] = (date.today() - d).days
    except Exception:
        app["duration"] = 0
    return app


def add_application(data):
    conn = get_connection()
    conn.execute(
        """INSERT INTO applications
           (job_desc, team, company, date_applied, status,
            cover_letter, resume, comment, success_chance, link)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
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
        ),
    )
    conn.commit()
    conn.close()


def update_application(app_id, data):
    conn = get_connection()
    conn.execute(
        """UPDATE applications SET
           job_desc=?, team=?, company=?, date_applied=?, status=?,
           cover_letter=?, resume=?, comment=?, success_chance=?, link=?
           WHERE id=?""",
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
            app_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_application(app_id):
    conn = get_connection()
    conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
    conn.commit()
    conn.close()


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
    row = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
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
        if a["status"] not in ("Select_Status", "Drafting_CV", "Not Applying")
    )
    rejected = sum(1 for a in apps if "Rejected" in a["status"])
    offers = sum(1 for a in apps if a["status"] == "Offer_recieved")
    success_rate = round((offers / submitted * 100), 1) if submitted else 0
    pending = [a for a in apps if a["status"] in PENDING_STATUSES]
    return {
        "total": total,
        "submitted": submitted,
        "rejected": rejected,
        "offers": offers,
        "success_rate": success_rate,
        "pending": pending,
    }


def get_status_counts(year=None):
    apps = get_applications(year=year)
    counts = {}
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
            if a["status"] not in ("Select_Status", "Drafting_CV", "Not Applying")
        )
        offers = sum(1 for a in apps if a["status"] == "Offer_recieved")
        result[str(y)] = round((offers / submitted * 100), 1) if submitted else 0
    return result


def get_company_note_frequency():
    """Return top notes/sectors from companies table."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT note FROM companies WHERE note IS NOT NULL AND note != ''"
    ).fetchall()
    conn.close()
    freq = {}
    for r in rows:
        note = r["note"].strip()
        if note:
            freq[note] = freq.get(note, 0) + 1
    return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15])

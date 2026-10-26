"""Shared pytest fixtures.

Every test session uses a throwaway SQLite file, single-user mode and no
background scheduler, so tests never touch a real database.
"""

import os
import sys
import tempfile

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="job-tracker-tests-")
os.environ["DB_PATH"] = os.path.join(_TMP_DIR, "test.db")
os.environ["DEPLOYMENT_MODE"] = "local"
os.environ["JOB_TRACKER_DISABLE_SCHEDULER"] = "1"
os.environ.setdefault("SECRET_KEY", "test-secret")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402  (must come after DB_PATH is set)
from app import app as flask_app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """Start every test with no applications or companies and onboarding done."""
    conn = db.get_connection()
    for table in ("status_history", "reminders", "applications", "companies"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    db.set_setting("onboarding_complete", "1")
    db.set_setting("login_enabled", "0")
    db.set_setting("latest_release_tag", "")
    yield


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client

"""Files attached to an application: the CV and cover letter that were sent.

Rows live in the ``attachments`` table; the files themselves are stored in an
``attachments`` folder next to the database (so the Docker data volume and
NAS backups already cover them) under random names, never the uploaded name.
"""

import logging
import os
import uuid
from datetime import datetime

from .connection import DB_PATH, get_connection

logger = logging.getLogger(__name__)

ATTACHMENTS_DIR = os.path.join(os.path.dirname(DB_PATH), "attachments")

# What a CV or cover letter is usually saved as.
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ATTACHMENT_KINDS = ("CV / resume", "Cover letter", "Other")


def attachment_path(stored_name: str) -> str:
    return os.path.join(ATTACHMENTS_DIR, os.path.basename(stored_name))


def add_attachment(application_id: int, filename: str, data: bytes, kind: str = "") -> int:
    """Save *data* and record it against the application.  Returns the new id.

    The caller checks the extension, size and that the application belongs
    to the user.
    """
    ext = os.path.splitext(filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    with open(attachment_path(stored_name), "wb") as fh:
        fh.write(data)
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO attachments (application_id, kind, filename, stored_name, size, uploaded_at)"
        " VALUES (?,?,?,?,?,?)",
        (application_id, kind if kind in ATTACHMENT_KINDS else "Other", filename,
         stored_name, len(data), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_attachments(application_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM attachments WHERE application_id=? ORDER BY uploaded_at, id",
        (application_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attachment(attachment_id: int, user_id=None):
    """One attachment, only if its application belongs to *user_id* (when given)."""
    conn = get_connection()
    sql = ("SELECT t.* FROM attachments t JOIN applications a ON a.id = t.application_id"
           " WHERE t.id=?")
    params: list = [attachment_id]
    if user_id is not None:
        sql += " AND a.user_id=?"
        params.append(user_id)
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_attachment(attachment_id: int, user_id=None) -> bool:
    attachment = get_attachment(attachment_id, user_id=user_id)
    if not attachment:
        return False
    conn = get_connection()
    conn.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
    conn.commit()
    conn.close()
    _remove_file(attachment["stored_name"])
    return True


def remove_files_for_applications(application_ids: list, user_id=None):
    """Delete the stored files of applications that are about to be deleted.

    The rows go with the application (ON DELETE CASCADE); the files need
    removing by hand.
    """
    if not application_ids:
        return
    placeholders = ",".join("?" for _ in application_ids)
    sql = ("SELECT t.stored_name FROM attachments t JOIN applications a ON a.id = t.application_id"
           f" WHERE t.application_id IN ({placeholders})")
    params: list = list(application_ids)
    if user_id is not None:
        sql += " AND a.user_id=?"
        params.append(user_id)
    conn = get_connection()
    names = [r["stored_name"] for r in conn.execute(sql, params).fetchall()]
    conn.close()
    for name in names:
        _remove_file(name)


def _remove_file(stored_name: str):
    try:
        os.remove(attachment_path(stored_name))
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("Could not delete attachment file %s", stored_name)

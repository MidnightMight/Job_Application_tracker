"""Calendar feed: each application's next step as an all-day event.

Calendar apps can't log in, so the feed is reached through a private link
holding a random token, one per user, made (and replaced or turned off) in
Settings → General.  The token is stored as the setting
``calendar_token_<user id>`` (``calendar_token_0`` in single-user mode).
"""

import secrets
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, abort, url_for

import db
from .auth import current_user_id

bp = Blueprint("calendar_feed", __name__)

_TOKEN_PREFIX = "calendar_token_"


def _token_key(user_id) -> str:
    return f"{_TOKEN_PREFIX}{user_id or 0}"


def get_calendar_token(user_id) -> str:
    return db.get_setting(_token_key(user_id), "")


def new_calendar_token(user_id) -> str:
    token = secrets.token_urlsafe(24)
    db.set_setting(_token_key(user_id), token)
    return token


def remove_calendar_token(user_id):
    db.set_setting(_token_key(user_id), "")


def calendar_feed_url(user_id) -> str:
    token = get_calendar_token(user_id)
    return url_for("calendar_feed.feed", token=token, _external=True) if token else ""


def _user_for_token(token: str):
    """(found, user_id) for a feed token; user_id is None in single-user mode."""
    if len(token) < 20:
        return False, None
    for key, value in db.get_all_settings().items():
        if key.startswith(_TOKEN_PREFIX) and value and secrets.compare_digest(value, token):
            suffix = key[len(_TOKEN_PREFIX):]
            return True, (int(suffix) or None) if suffix.isdigit() else None
    return False, None


def _ics_text(value: str) -> str:
    """Escape text for an iCalendar property value."""
    return (value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Fold long lines at 74 characters, as RFC 5545 asks."""
    out = []
    while len(line) > 74:
        out.append(line[:74])
        line = " " + line[74:]
    out.append(line)
    return "\r\n".join(out)


def build_calendar(actions: list, app_url) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Job Application Tracker//Next steps//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Job applications",
        "X-PUBLISHED-TTL:PT1H",
    ]
    for a in actions:
        try:
            day = date.fromisoformat((a["next_action_date"] or "")[:10])
        except ValueError:
            continue
        what = (a.get("next_action") or "").strip() or "Next step"
        summary = f"{what} — {a.get('company') or 'Application'}"
        details = [a.get("job_desc") or "", (a.get("status") or "").replace("_", " "),
                   app_url(a["id"])]
        if a.get("link"):
            details.append(f"Job ad: {a['link']}")
        lines += [
            "BEGIN:VEVENT",
            f"UID:application-{a['id']}-next-step@job-tracker",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ics_text(summary)}",
            f"DESCRIPTION:{_ics_text(chr(10).join(d for d in details if d))}",
            f"URL:{app_url(a['id'])}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


@bp.route("/calendar/<token>.ics")
def feed(token):
    found, user_id = _user_for_token(token)
    if not found:
        abort(404)
    body = build_calendar(
        db.get_calendar_actions(user_id=user_id),
        lambda app_id: url_for("applications.application_detail", app_id=app_id, _external=True),
    )
    return Response(body, mimetype="text/calendar",
                    headers={"Content-Disposition": "inline; filename=job-applications.ics",
                             "Cache-Control": "no-store"})

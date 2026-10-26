"""Checking GitHub for a newer release of the app.

Release tags are compared leniently so the tags used so far all work:
``v1.2.2``, ``V1.2.4`` and ``V1.2.4A`` (a lettered re-release of 1.2.4,
which counts as newer than plain 1.2.4).

The latest result is cached in the settings table so pages can show an
"update available" badge without calling GitHub on every request.
"""

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime

import db

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^(\d+(?:\.\d+)*)([A-Za-z]*)")


def parse_version(tag: str):
    """Return (numbers, suffix) for a tag like 'V1.2.4A', or None if unreadable."""
    text = (tag or "").strip().lstrip("vV").strip()
    match = _VERSION_RE.match(text)
    if not match:
        return None
    numbers = [int(part) for part in match.group(1).split(".")]
    return numbers, match.group(2).upper()


def is_newer(latest: str, current: str) -> bool:
    """True when *latest* is a higher version than *current*."""
    parsed_latest, parsed_current = parse_version(latest), parse_version(current)
    if not parsed_latest or not parsed_current:
        return False
    l_nums, l_suffix = parsed_latest
    c_nums, c_suffix = parsed_current
    width = max(len(l_nums), len(c_nums))
    l_nums = l_nums + [0] * (width - len(l_nums))
    c_nums = c_nums + [0] * (width - len(c_nums))
    if l_nums != c_nums:
        return l_nums > c_nums
    return l_suffix > c_suffix


def display_version(tag: str) -> str:
    """'V1.2.4A' -> '1.2.4A' (for showing next to a 'v')."""
    return (tag or "").strip().lstrip("vV")


def fetch_latest_release(repo: str, timeout: int = 8) -> dict:
    """Return the latest GitHub release as {'tag', 'url'}.  Raises urllib errors."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Job-Tracker-App"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return {
        "tag": data.get("tag_name", ""),
        "url": data.get("html_url") or f"https://github.com/{repo}/releases",
    }


def store_latest_release(tag: str, url: str) -> None:
    db.set_setting("latest_release_tag", tag)
    db.set_setting("latest_release_url", url)
    db.set_setting("latest_release_checked_at", datetime.now().isoformat(timespec="seconds"))


def refresh_latest_release(repo: str) -> dict | None:
    """Fetch and cache the latest release.  Returns it, or None on any failure."""
    if db.get_setting("update_check_enabled", "1") != "1":
        return None
    try:
        release = fetch_latest_release(repo)
    except Exception as exc:  # network down, rate limit, no releases yet…
        logger.info("Update check skipped: %s", exc)
        return None
    store_latest_release(release["tag"], release["url"])
    return release


def cached_update_info(current_version: str) -> dict:
    """What the templates need to show an 'update available' badge."""
    tag = db.get_setting("latest_release_tag", "")
    return {
        "update_available": bool(tag) and is_newer(tag, current_version),
        "latest_version": display_version(tag),
        "latest_release_url": db.get_setting("latest_release_url", ""),
    }

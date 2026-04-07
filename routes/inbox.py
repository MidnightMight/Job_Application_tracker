"""Inbox (reminders) routes."""

from flask import Blueprint, flash, redirect, render_template, url_for

import db

bp = Blueprint("inbox", __name__)


@bp.route("/inbox")
def inbox():
    reminders = db.get_reminders()
    return render_template("inbox.html", reminders=reminders)


@bp.route("/inbox/dismiss/<int:reminder_id>", methods=["POST"])
def dismiss_reminder(reminder_id):
    db.dismiss_reminder(reminder_id)
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/dismiss-all", methods=["POST"])
def dismiss_all_reminders():
    db.dismiss_all_reminders()
    flash("All reminders dismissed.", "success")
    return redirect(url_for("inbox.inbox"))

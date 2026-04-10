"""Inbox (reminders) routes."""

from flask import Blueprint, flash, redirect, render_template, url_for

import db
from .auth import login_required, current_user_id

bp = Blueprint("inbox", __name__)


@bp.route("/inbox")
@login_required
def inbox():
    user_id = current_user_id()
    reminders = db.get_reminders(user_id=user_id)
    return render_template("inbox.html", reminders=reminders)


@bp.route("/inbox/dismiss/<int:reminder_id>", methods=["POST"])
@login_required
def dismiss_reminder(reminder_id):
    db.dismiss_reminder(reminder_id)
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/dismiss-all", methods=["POST"])
@login_required
def dismiss_all_reminders():
    user_id = current_user_id()
    db.dismiss_all_reminders(user_id=user_id)
    flash("All reminders dismissed.", "success")
    return redirect(url_for("inbox.inbox"))

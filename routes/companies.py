"""Company CRUD and bulk-delete routes."""

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for,
)

import db
from .auth import login_required, current_user_id

bp = Blueprint("companies", __name__)


def _company_view_context():
    login_enabled = db.get_setting("login_enabled", "0") == "1"
    pool_enabled = db.get_setting("company_pool_enabled", "0") == "1"
    user_id = session.get("user_id") if login_enabled else None
    return user_id, pool_enabled


@bp.route("/companies")
@login_required
def companies():
    user_id, pool_enabled = _company_view_context()
    companies_list = db.get_companies(user_id=user_id, pool_enabled=pool_enabled)
    sector_freq = db.get_company_note_frequency()
    return render_template(
        "companies.html",
        companies=companies_list,
        years=db.get_dynamic_years(),
        sector_freq=sector_freq,
        pool_enabled=pool_enabled,
        current_user_id=user_id,
    )


@bp.route("/company/<int:company_id>")
@login_required
def company_detail(company_id):
    company = db.get_company(company_id)
    if not company:
        flash("Company not found.", "danger")
        return redirect(url_for("companies.companies"))
    login_enabled = db.get_setting("login_enabled", "0") == "1"
    user_id = session.get("user_id") if login_enabled else None
    status_options = db.get_status_options(user_id=user_id)
    apps_data = db.get_applications_for_company(company["company_name"], user_id=user_id)

    # Sort each per-year bucket by status order then date
    order = {name: i for i, name in enumerate(status_options)}
    _UNKNOWN = 10_000
    for bucket in apps_data["by_year"].values():
        for lst in (bucket["active"], bucket["archived"]):
            lst.sort(key=lambda a: (
                order.get(a.get("status", ""), _UNKNOWN),
                a.get("date_applied") or "",
            ))

    return render_template(
        "company_detail.html",
        company=company,
        apps_data=apps_data,
        status_options=status_options,
        years=db.get_dynamic_years(user_id=user_id),
    )


@bp.route("/company/add", methods=["GET", "POST"])
@login_required
def add_company():
    if request.method == "POST":
        login_enabled = db.get_setting("login_enabled", "0") == "1"
        user_id = session.get("user_id") if login_enabled else None
        db.add_company(request.form, user_id=user_id)
        flash("Company added successfully.", "success")
        return redirect(url_for("companies.companies"))
    return render_template(
        "company_form.html", company=None, years=db.get_dynamic_years(), action="Add"
    )


@bp.route("/company/edit/<int:company_id>", methods=["GET", "POST"])
@login_required
def edit_company(company_id):
    company = db.get_company(company_id)
    if not company:
        flash("Company not found.", "danger")
        return redirect(url_for("companies.companies"))
    if request.method == "POST":
        db.update_company(company_id, request.form)
        flash("Company updated.", "success")
        return redirect(url_for("companies.companies"))
    return render_template(
        "company_form.html", company=company, years=db.get_dynamic_years(), action="Edit"
    )


@bp.route("/company/delete/<int:company_id>", methods=["POST"])
@login_required
def delete_company(company_id):
    db.delete_company(company_id)
    flash("Company deleted.", "warning")
    return redirect(url_for("companies.companies"))


@bp.route("/companies/bulk-delete", methods=["POST"])
@login_required
def bulk_delete_companies():
    raw_ids = request.form.getlist("selected_ids")
    selected_ids = []
    for x in raw_ids:
        try:
            n = int(x)
            if n > 0:
                selected_ids.append(n)
        except (ValueError, TypeError):
            pass
    if not selected_ids:
        flash("No companies selected.", "warning")
        return redirect(url_for("companies.companies"))
    count = db.bulk_delete_companies(selected_ids)
    flash(f"Deleted {count} company record(s).", "warning")
    return redirect(url_for("companies.companies"))

from flask import Flask, render_template, request, redirect, url_for, flash
import os
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "job-tracker-secret-key-change-me")

db.init_db()


@app.context_processor
def inject_globals():
    from datetime import date
    return {"years": db.YEARS, "current_year_for_footer": date.today().year}


@app.route("/")
def dashboard():
    current_year = 2024
    stats = db.get_stats(year=current_year)
    status_counts = db.get_status_counts(year=current_year)
    apps_per_year = db.get_apps_per_year()
    success_per_year = db.get_success_rate_per_year()
    keyword_freq = db.get_company_note_frequency()
    return render_template(
        "dashboard.html",
        stats=stats,
        status_counts=status_counts,
        apps_per_year=apps_per_year,
        success_per_year=success_per_year,
        keyword_freq=keyword_freq,
        current_year=current_year,
        years=db.YEARS,
    )


@app.route("/year/<int:year>")
def year_view(year):
    status_filter = request.args.get("status", "")
    apps = db.get_applications(year=year, status=status_filter if status_filter else None)
    stats = db.get_stats(year=year)
    return render_template(
        "year_view.html",
        apps=apps,
        year=year,
        stats=stats,
        years=db.YEARS,
        status_options=db.STATUS_OPTIONS,
        selected_status=status_filter,
    )


@app.route("/companies")
def companies():
    companies_list = db.get_companies()
    sector_freq = db.get_company_note_frequency()
    return render_template(
        "companies.html",
        companies=companies_list,
        years=db.YEARS,
        sector_freq=sector_freq,
    )


@app.route("/company/add", methods=["GET", "POST"])
def add_company():
    if request.method == "POST":
        db.add_company(request.form)
        flash("Company added successfully.", "success")
        return redirect(url_for("companies"))
    return render_template("company_form.html", company=None, years=db.YEARS, action="Add")


@app.route("/company/edit/<int:company_id>", methods=["GET", "POST"])
def edit_company(company_id):
    company = db.get_company(company_id)
    if not company:
        flash("Company not found.", "danger")
        return redirect(url_for("companies"))
    if request.method == "POST":
        db.update_company(company_id, request.form)
        flash("Company updated.", "success")
        return redirect(url_for("companies"))
    return render_template("company_form.html", company=company, years=db.YEARS, action="Edit")


@app.route("/company/delete/<int:company_id>", methods=["POST"])
def delete_company(company_id):
    db.delete_company(company_id)
    flash("Company deleted.", "warning")
    return redirect(url_for("companies"))


@app.route("/application/add", methods=["GET", "POST"])
def add_application():
    if request.method == "POST":
        db.add_application(request.form)
        flash("Application added.", "success")
        year = request.form.get("date_applied", "")[:4] or "2024"
        return redirect(url_for("year_view", year=year))
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=None,
        companies=companies_list,
        status_options=db.STATUS_OPTIONS,
        action="Add",
    )


@app.route("/application/edit/<int:app_id>", methods=["GET", "POST"])
def edit_application(app_id):
    application = db.get_application(app_id)
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        db.update_application(app_id, request.form)
        flash("Application updated.", "success")
        year = request.form.get("date_applied", "")[:4] or "2024"
        return redirect(url_for("year_view", year=year))
    companies_list = db.get_companies()
    return render_template(
        "application_form.html",
        app=application,
        companies=companies_list,
        status_options=db.STATUS_OPTIONS,
        action="Edit",
    )


@app.route("/application/delete/<int:app_id>", methods=["POST"])
def delete_application(app_id):
    application = db.get_application(app_id)
    year = application["date_applied"][:4] if application else "2024"
    db.delete_application(app_id)
    flash("Application deleted.", "warning")
    return redirect(url_for("year_view", year=year))


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

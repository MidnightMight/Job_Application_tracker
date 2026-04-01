#!/usr/bin/env python3
"""CLI script for job tracker stats. Run with: python run_script.py [options]"""

import argparse
import csv
import sys
import os

# Ensure we can import database from the same directory
sys.path.insert(0, os.path.dirname(__file__))
import database as db


def print_header(text):
    width = 60
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def print_stats(year=None):
    label = f"Year {year}" if year else "All Years"
    print_header(f"Job Tracker Stats — {label}")

    stats = db.get_stats(year=year)
    print(f"  Total applications : {stats['total']}")
    print(f"  Submitted          : {stats['submitted']}")
    print(f"  Rejected           : {stats['rejected']}")
    print(f"  Offers received    : {stats['offers']}")
    print(f"  Success rate       : {stats['success_rate']}%")
    print(f"  Pending / active   : {len(stats['pending'])}")

    print_header("Applications by Status")
    counts = db.get_status_counts(year=year)
    for status, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * cnt
        print(f"  {status:<25} {cnt:>3}  {bar}")

    if not year:
        print_header("Applications per Year")
        per_year = db.get_apps_per_year()
        for yr, cnt in per_year.items():
            bar = "█" * cnt
            print(f"  {yr}  {cnt:>3}  {bar}")

        print_header("Success Rate per Year")
        sr = db.get_success_rate_per_year()
        for yr, rate in sr.items():
            print(f"  {yr}  {rate:.1f}%")

    if stats["pending"]:
        print_header("Pending / Active Applications")
        for a in stats["pending"]:
            print(f"  [{a['status']:<25}] {a['company']:<20} — {a['date_applied']}  ({a['duration']}d)")


def print_company_stats(company_name):
    companies = db.get_companies()
    matches = [c for c in companies if company_name.lower() in c["company_name"].lower()]
    if not matches:
        print(f"No company matching '{company_name}' found.")
        return
    print_header(f"Company Search: '{company_name}'")
    for c in matches:
        applied_years = [
            str(y) for y in db.YEARS
            if c.get(f"applied_{y}", 0)
        ]
        print(f"  {c['company_name']:<30}  Note: {c['note'] or '—'}")
        print(f"    Applied years: {', '.join(applied_years) if applied_years else 'None'}")


def export_csv(year=None, filename=None):
    apps = db.get_applications(year=year)
    if not filename:
        filename = f"applications_{year or 'all'}.csv"
    fields = [
        "id", "job_desc", "team", "company", "date_applied", "status",
        "cover_letter", "resume", "duration", "comment", "success_chance", "link",
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(apps)
    print(f"Exported {len(apps)} applications to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Job Tracker CLI — view stats or export data"
    )
    parser.add_argument("--year", type=int, help="Filter by year (e.g. 2024)")
    parser.add_argument("--company", type=str, help="Search companies by name")
    parser.add_argument(
        "--export-csv", metavar="FILE", nargs="?", const="__auto__",
        help="Export applications to CSV (optional filename)"
    )
    args = parser.parse_args()

    db.init_db()

    if args.company:
        print_company_stats(args.company)
        return

    if args.export_csv is not None:
        filename = None if args.export_csv == "__auto__" else args.export_csv
        export_csv(year=args.year, filename=filename)
        return

    print_stats(year=args.year)


if __name__ == "__main__":
    main()

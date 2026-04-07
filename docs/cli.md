# CLI Reference — Job Application Tracker

`run_script.py` provides a read-only command-line interface for querying and
exporting your application data without starting the web server.

---

## Usage

```
python run_script.py [OPTIONS]
```

Run from the project root with the virtual environment active.

---

## Options

| Option | Argument | Description |
|---|---|---|
| *(none)* | | Print an all-years summary table |
| `--year` | `YYYY` | Filter to a single year |
| `--company` | `"Name"` | Filter to a specific company (case-insensitive) |
| `--export-csv` | `[filename]` | Export results to CSV (default: `applications.csv`) |

---

## Examples

```bash
# All-year summary
python run_script.py

# Single-year summary
python run_script.py --year 2025

# Filter by company
python run_script.py --company "Acme Engineering"

# Export everything to CSV
python run_script.py --export-csv

# Export a specific year to a named file
python run_script.py --year 2025 --export-csv applications_2025.csv
```

---

## Output Format

The summary output is a plain-text table:

```
Company               Role                  Status              Date Applied
----                  ----                  ------              ------------
Acme Engineering      Graduate Engineer     Submitted           2025-03-10
Beta Consulting       Graduate Engineer     Interview Scheduled 2025-03-15
…
```

CSV export includes all application fields including `duration` (days since
applied), `ai_fit_score`, `industry`, and `job_expiry_date`.

---

## Notes

- The script reads `jobs.db` from the project folder (or the path set by the
  `DB_PATH` environment variable).
- No Flask server needs to be running.
- The script is read-only — it never writes to the database.

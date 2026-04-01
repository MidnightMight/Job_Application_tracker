# Job Tracker

A local web application for tracking job applications, company history, stage
progression and success rates across multiple years.

---

## Features

- **Dashboard** – summary stats, Chart.js charts (status breakdown, apps per
  year, success rate trend, sector keyword frequency)
- **Year views** – filterable table of every application for a given year,
  pipeline progress bar, per-year stats
- **Company tracker** – cross-year applied history for 80+ companies with
  sector grouping
- **CRUD** – add / edit / delete applications and companies
- **CLI script** – `run_script.py` prints stats without starting the server

---

## Quick start

### Option 1 – Plain Python (local machine)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server (auto-creates jobs.db and seeds sample data)
python app.py

# 3. Open in browser
#    http://localhost:5000
```

Run as a CLI script instead:

```bash
python run_script.py               # all-year summary
python run_script.py --year 2024   # one year
python run_script.py --company "Acme Engineering" # one company
python run_script.py --export-csv out.csv
```

---

### Option 2 – Docker (Windows / macOS / Linux)

> Requires **Docker Desktop** (Windows/macOS) or the Docker Engine (Linux).

```powershell
# Build and start (detached)
docker compose up -d --build

# Open in browser
start http://localhost:5000      # Windows
open  http://localhost:5000      # macOS

# Stop
docker compose down
```

The SQLite database is stored in a named Docker volume (`job_tracker_data`) so
it survives container restarts and image upgrades.

To change the host port (e.g. `8080`), edit `docker-compose.yml`:

```yaml
ports:
  - "8080:5000"   # host:container
```

#### Environment variables

| Variable     | Default                       | Purpose                          |
|--------------|-------------------------------|----------------------------------|
| `SECRET_KEY` | `change-me-in-production`     | Flask session signing key        |
| `DB_PATH`    | `/data/jobs.db`               | Path to the SQLite database      |
| `PORT`       | `5000`                        | Port the server listens on       |
| `FLASK_DEBUG`| `0`                           | Set to `1` to enable debug mode  |

Set them in `docker-compose.yml` under `environment:`, or pass via
`docker run -e SECRET_KEY=...`.

---

### Option 3 – Synology Container Manager

1. Install **Container Manager** from Package Center (DSM 7.2+).
2. In Container Manager go to **Project → Create → Upload compose file**.
3. Upload `docker-compose.yml` from this repository.
4. Click **Build** – Synology pulls the image and starts the container.
5. Access the app at `http://<your-NAS-IP>:5000`.

The data volume is managed automatically by Synology and persists across
reboots and package updates.

> **Tip:** To expose the tracker only on your LAN, leave port `5000` as-is and
> do not forward it through your router.

---

## Project structure

```
app.py                   Flask application (all routes)
database.py              SQLite schema, seed data, query helpers
run_script.py            CLI script mode
requirements.txt         Python dependencies
Dockerfile               Container image definition
docker-compose.yml       Single-command deployment
.dockerignore            Files excluded from the Docker build context
templates/
  base.html              Bootstrap 5 layout + navigation
  dashboard.html         Main dashboard with Chart.js charts
  year_view.html         Per-year application table + pipeline bar
  companies.html         Company tracker with sector chart
  application_form.html  Add / edit application
  company_form.html      Add / edit company
static/
  style.css              Custom styles and status-coloured badges
```

---

## Status values

`Select_Status` · `Drafting_CV` · `Submitted` · `Online_assessment` ·
`Awaiting_Response` · `Interview_scheduled` · `Interview_inperson` ·
`Rejected` · `Likely Rejected` · `Offer_recieved` · `Offer_rejected` ·
`Not Applying` · `EOI`

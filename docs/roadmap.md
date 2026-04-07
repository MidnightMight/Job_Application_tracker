# Roadmap & Feasibility Notes — Job Application Tracker

Potential enhancements that are technically feasible but not yet implemented.

---

## Packaged Executable

Tools such as **PyInstaller** or **Nuitka** can bundle the entire application
(Python runtime included) into a single `.exe` or `.app` binary, making
installation completely dependency-free for end users.

---

## Browser Extension

A Manifest V3 extension could pre-fill the Add Application form by reading the
job title, company, and URL from job boards (LinkedIn, Seek, Indeed).

See [`FEATURES.md`](../FEATURES.md#6-browser-extension-research) for a full
research summary and recommended architecture.

---

## Email / Calendar Integration

Parsing interview confirmation emails and automatically updating the application
status is technically feasible using the Gmail or Outlook API, though it requires
OAuth setup and user consent flows.

---

## REST API

A JSON endpoint (`POST /api/applications`, protected by an API key) would enable
browser-extension integration, mobile shortcuts, and third-party automation tools.

---

## AI Enhancements (planned)

- **Probability of success** — combine the AI fit score with the application's
  status history and pipeline-stage weights to calculate a data-driven
  probability estimate.
- **Company industry auto-detection** — use the LLM to suggest an industry/sector
  for a company based on its name, then let the user confirm or correct it.
- **Job advert expiry prediction** — use the LLM to infer likely expiry dates
  from the job description text.
- **Structured notes** — when generating a fit summary, produce bullet points
  rather than paragraphs for easier scanning.
- **Toggle AI features** — allow individual AI sub-features (fill, fit, industry
  detection, expiry prediction) to be toggled on/off independently in Settings.

---

## Multi-Device Sync

A lightweight sync mechanism (e.g. WebDAV, Git-backed SQLite, or a shared Docker
volume over a VPN) would allow the same database to be accessed from multiple
devices.

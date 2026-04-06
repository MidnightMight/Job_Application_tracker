# User Guide — Job Application Tracker

A practical reference for everyday use: adding jobs, tracking progress, using
bulk operations, searching, and exporting your data.

---

## Table of Contents

1. [Dashboard overview](#1-dashboard-overview)
2. [Adding a job application](#2-adding-a-job-application)
3. [Editing and deleting an application](#3-editing-and-deleting-an-application)
4. [Viewing the application detail page](#4-viewing-the-application-detail-page)
5. [Year view and filtering](#5-year-view-and-filtering)
6. [Bulk operations](#6-bulk-operations)
7. [Global search](#7-global-search)
8. [Company tracker](#8-company-tracker)
9. [Custom statuses](#9-custom-statuses)
10. [Reminder inbox](#10-reminder-inbox)
11. [Importing from CSV or Excel](#11-importing-from-csv-or-excel)
12. [Exporting data](#12-exporting-data)
13. [AI assistant (Ollama)](#13-ai-assistant-ollama)
14. [Dark / light theme](#14-dark--light-theme)
15. [Keyboard shortcuts and tips](#15-keyboard-shortcuts-and-tips)

---

## 1. Dashboard overview

The dashboard is the first page you see at `http://localhost:5000`. It shows a
summary for the current year and charts for all tracked years.

| Card / chart | What it shows |
|---|---|
| **Total** | All applications in the current year |
| **Submitted** | Applications past Drafting_CV / Select_Status / Not_Applying |
| **Offers** | Applications with status Offer_Received |
| **Success Rate** | Offers ÷ Submitted × 100 |
| **Status breakdown** | Bar chart of all applications by status |
| **Applications per year** | Bar chart comparing annual totals |
| **Success rate trend** | Line chart of yearly offer rates |
| **Top keywords** | Most common company notes / sectors |
| **Pending** | Table of applications still awaiting a response |

---

## 2. Adding a job application

1. Click the **+ New Application** button in the navigation bar (or
   **Add** on a year-view page).
2. Fill in the form:

| Field | Required | Description |
|---|---|---|
| **Company** | ✅ | Employer name |
| **Date Applied** | ✅ | Date you submitted (or intend to submit). Click **Today** to autofill. |
| **Job Title / Role** | — | Position title |
| **Team** | — | Department or team name |
| **Status** | — | Current stage (defaults to `Select_Status`) |
| **Cover Letter** | — | Tick if you included a cover letter |
| **Resume / CV** | — | Tick if you sent a CV (ticked by default) |
| **Link** | — | URL to the job posting |
| **Contact** | — | Recruiter or hiring manager name |
| **Success Chance** | — | Your personal estimate (0–1 or percentage) |
| **Comment** | — | Short note about the application |
| **Additional Notes** | — | Longer free-text notes |

3. Click **Save Application**. The application is added to the year matching
   **Date Applied**.

> **Tip:** If you leave a required field blank, a validation modal highlights
> the missing field rather than silently failing.

---

## 3. Editing and deleting an application

**Edit:** Click the **pencil icon** on any row in a year view, or click
**Edit** on the detail page.

**Delete:** Click the **bin icon** on any row. A confirmation prompt appears.
Deletion also removes the status timeline history for that application.

---

## 4. Viewing the application detail page

Click the **company name** or the **eye icon** on any row to open the detail page.

The detail page shows:

- All fields including additional notes and contact
- **Status timeline** — every status change with the date/time and how many
  days elapsed between each stage. The dots are colour-coded to match the status
  badge colours.
- **Quick-edit status** button to update the current stage directly

---

## 5. Year view and filtering

Click **By Year** in the navigation bar and choose a year to see all
applications for that year in a table.

**Filter by status:**

1. Use the **Filter by Status** dropdown above the table.
2. Click **Apply** to show only applications with that status.
3. Click **Clear** to remove the filter.

**Columns in the table:**

| Column | Description |
|---|---|
| **Company** | Employer name (links to detail page) |
| **Role / Team** | Job title and team |
| **Applied** | Date applied |
| **Last Contact** | Last contact date (🔵 icon) or last status change (⏰ icon) |
| **Status** | Colour-coded status badge |
| **CL** | Cover letter ✔ / ✘ |
| **CV** | Resume ✔ / ✘ |
| **Days** | Days since application date (yellow > 60 days, grey > 120 days) |
| **Chance** | Success chance estimate |
| **Contact** | Recruiter / contact name |
| **Comment** | Short note (truncated) |
| **Link** | External job posting link |

---

## 6. Bulk operations

The bulk-action toolbar above the applications table lets you update or delete
multiple rows at once — useful for post-rejection cleanup.

### Selecting rows

| Method | How |
|---|---|
| Tick individual rows | Click the checkbox at the left of each row |
| Select all | Click **All** in the toolbar, or tick the header checkbox |
| Deselect all | Click **None** in the toolbar |

The **N selected** counter updates in real time.

### Available bulk actions

| Action | How to use |
|---|---|
| **Set Status** | Choose a status from the dropdown, click **Set** |
| **Set Date Applied** | Pick a date, click **Set** |
| **Set Last Contact** | Pick a date, click **Set** |
| **Set Cover Letter** | Choose Yes/No, click **Set** |
| **Set Resume** | Choose Yes/No, click **Set** |
| **Delete Selected** | Click **Delete Selected** — a confirmation prompt appears |

> **Tip:** To mark all rejections in one go — filter the year view to
> `Submitted` or `Awaiting_Response`, select all, choose `Rejected` from the
> status dropdown, click **Set**.

---

## 7. Global search

The **search bar** in the navigation bar (🔍 icon) searches across *all years*
at once.

Searches these fields:
- Company name
- Job title / role
- Team
- Comment
- Additional notes
- Contact

**To search:**

1. Type a keyword into the search box in the navbar and press **Enter**, or
   go to `/search` directly.
2. Results show the company, role, year, status, and a snippet of the comment /
   notes.
3. Click the company name or **eye icon** to open the detail page.
4. Click the year link to jump to the year view for that application.

> **Minimum query length:** 2 characters.

---

## 8. Company tracker

Go to **Companies** in the navigation bar to see a table of all companies with:

- Notes / sector
- Applied columns for each tracked year (2023–2027)

**Add a company:** Click **Add Company** and fill in the name and optional note.

**Edit / delete:** Use the icons on the right of each row.

When **Company List Pooling** is enabled (Settings → General), all users share
the company list but private notes from other users are hidden.

---

## 9. Custom statuses

Go to **Settings → Statuses** to manage your status list.

- **Add:** Type a name in the input field and click **Add Status**. Spaces are
  automatically converted to underscores.
- **Delete:** Click the bin icon next to a status. Deletion is blocked while
  any application uses that status — update those applications first.

**Default statuses:**

| Status | Meaning |
|---|---|
| `Select_Status` | Placeholder — not yet categorised |
| `Drafting_CV` | Preparing application materials |
| `Submitted` | Application submitted |
| `Online_Assessment` | Online test or coding challenge |
| `Awaiting_Response` | Waiting to hear back |
| `Interview_Scheduled` | Interview confirmed |
| `Interview_In_Person` | In-person interview stage |
| `Offer_Received` | Offer received 🎉 |
| `Offer_Rejected` | Offer declined |
| `Rejected` | Application unsuccessful |
| `Likely_Rejected` | No response for a long time |
| `Not_Applying` | Decided not to proceed |
| `EOI` | Expression of interest |

---

## 10. Reminder inbox

The **bell icon** in the navbar shows a red badge when there are unread
reminders. Click **Inbox** to view them.

A reminder is automatically created when an application has been in a pending
status (e.g. `Submitted`, `Awaiting_Response`) for longer than the configured
threshold (default: **3 days**).

**Configure reminders:**

1. Go to **Settings → General**.
2. Toggle **Enable reminder notifications** on or off.
3. Change the **Reminder threshold (days)** — must be ≥ 1.
4. Click **Save**.

**Dismiss reminders:**

- Click **Dismiss** next to a single reminder.
- Click **Dismiss All** at the top to clear everything at once.

---

## 11. Importing from CSV or Excel

1. Click **Import CSV** in the navigation bar.
2. **Step 1 — Upload:** Select a `.csv` or `.xlsx` file. The first row must be
   column headers (any header names are fine).
3. **Step 2 — Map Columns:** Assign each detected column to an application
   field using the dropdowns. Auto-guessing fills in common column names.
   A preview of the first five rows helps you confirm the mapping.
4. Click **Import Applications**.

**Required fields per row:** `company` and `date_applied`

**Accepted date formats:** `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`, `MM/DD/YYYY`

A results page shows imported vs. skipped rows and the reason for any skipped rows.

---

## 12. Exporting data

Go to **Export** in the navigation bar.

| Export | Format | Filters |
|---|---|---|
| Applications | CSV | Year, status, company name |
| Company list | CSV | — |
| Full database | SQLite `.db` | — |

**To migrate to a new device:** Download the full database, copy it to the new
installation folder, rename it `jobs.db`, and restart the app.

---

## 13. AI assistant (Ollama)

> Available in Docker / server mode only.

The AI assistant uses a locally running [Ollama](https://ollama.com) server —
your data never leaves your machine.

### Setup

1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull a model: `ollama pull llama3` (or `mistral`, `phi3`, etc.)
3. Go to **Settings → AI Assistant**.
4. Enable **Ollama AI Assistant**, set the server URL and model name.
5. Click **Test** to verify the connection, then **Save AI Settings**.

### Using AI Fill

On the **Add / Edit Application** form, paste a job description into the
**Job Description** field and click **AI Fill**. The assistant extracts and
fills in the role, company, and team fields automatically.

### Smart Job Fit Analysis

Enable **Smart Job Fit Analysis** in Settings → AI Assistant. Once enabled:

1. Fill in your profile (Skills, Experience, Summary) on the same page — or
   upload your CV/résumé as a PDF to extract the text automatically.
2. After AI Fill runs, the app compares the job requirements against your
   profile and shows a match score, skill gaps, and a recommendation.

---

## 14. Dark / light theme

Click the **moon 🌙 / sun ☀️ icon** in the navigation bar to toggle between
dark and light themes. Your preference is saved in your browser and persists
across sessions and page reloads.

- **Moon icon** = currently light → click to switch to dark
- **Sun icon** = currently dark → click to switch to light

---

## 15. Keyboard shortcuts and tips

| Tip | How |
|---|---|
| **Today button** | On any date field, click the **Today** button to fill today's date without opening the calendar |
| **Quick search** | Press **/** or click the search box in the navbar to jump straight to global search |
| **Bulk reject** | Year view → filter by `Awaiting_Response` → select all → set status to `Rejected` → Set |
| **Jump to year** | Click a year badge on the dashboard quick-nav or use By Year in the navbar |
| **Offline access (PWA)** | On a server / Docker deployment, add the app to your home screen for fast access and cached offline pages |

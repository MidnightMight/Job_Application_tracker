# Application Statuses — Job Application Tracker

## Default Statuses

These statuses are seeded into every new installation.  Protected statuses (🔒)
cannot be deleted; they are the core workflow states that the application logic
depends on.

| Status                 | Display label            | Meaning                                           | Protected |
|------------------------|--------------------------|---------------------------------------------------|-----------|
| `Select_Status`        | Select Status            | Placeholder — not yet categorised                 | 🔒        |
| `Drafting_Application` | Drafting Application     | Writing the application cover letter / form       | 🔒        |
| `Drafting_CV`          | Drafting CV              | Preparing / updating the résumé or CV             |           |
| `Submitted`            | Submitted                | Application submitted / applied                   | 🔒        |
| `Online_Assessment`    | Online Assessment        | Online test, coding challenge, or psychometric    |           |
| `Awaiting_Response`    | Awaiting Response        | Waiting to hear back after submission             |           |
| `Interview_Scheduled`  | Interview Scheduled      | Interview date confirmed                          |           |
| `Interview_In_Person`  | Interview In Person      | In-person interview stage                         |           |
| `Offer_Received`       | Offer Received           | Offer of employment received                      | 🔒        |
| `Offer_Rejected`       | Offer Rejected           | Offer declined by the applicant                   | 🔒        |
| `Rejected`             | Rejected                 | Application unsuccessful                          | 🔒        |
| `Likely_Rejected`      | Likely Rejected          | No response for an extended period                |           |
| `Not_Applying`         | Not Applying             | Decided not to proceed with this application      | 🔒        |
| `Job_Expired`          | Job Expired              | The job advertisement has closed / expired        | 🔒        |
| `EOI`                  | EOI                      | Expression of interest submitted                  |           |

---

## Protected Status Rules

A status is **protected** when it is listed in `db/statuses.py:PROTECTED_STATUSES`.

- The **Settings → Statuses** page shows a 🔒 badge next to protected statuses
  and disables the delete button for them.
- `db.delete_status()` raises an error message (not an exception) if you attempt
  to delete a protected status via the API.
- Protected statuses are **not** removed if you re-seed the database.

### Why these eight?

| Status            | Reason                                                                 |
|-------------------|------------------------------------------------------------------------|
| `Select_Status`   | Default for new records; removing it would break the add form         |
| `Drafting_Application` | Core start-of-pipeline state                                   |
| `Submitted`       | Primary success metric — "submitted" count appears on the dashboard   |
| `Rejected`        | Used for the rejection rate calculation                               |
| `Offer_Received`  | Used for the offers / success rate calculation                        |
| `Offer_Rejected`  | Terminal positive state; paired with Offer_Received                  |
| `Not_Applying`    | Opt-out state; prevents spurious pending reminders                    |
| `Job_Expired`     | Marks dead postings; prevents spurious pending reminders              |

---

## Adding Custom Statuses

1. Go to **Settings** → **Statuses** in the navigation bar.
2. Enter a name in the **Add New Status** form.  Spaces are automatically
   converted to underscores.
3. Click **Add Status**.

Custom statuses can be deleted at any time as long as no application is
currently using them.

---

## Status Naming Convention

All status values use **Title_Snake_Case** (e.g. `Interview_Scheduled`).
Templates display them with `| replace('_', ' ')` so they render as natural
English.  CSS badge classes use the same convention (`status-Interview_Scheduled`).

---

## Pending Statuses (for Reminders)

The reminder system watches applications that are in a "pending" state for longer
than the configured threshold.  The current pending set is defined in
`db/connection.py:PENDING_STATUSES`:

```
Drafting_Application, Drafting_CV, Submitted,
Online_Assessment, Awaiting_Response,
Interview_Scheduled, Interview_In_Person, EOI
```

Applications in `Rejected`, `Not_Applying`, `Job_Expired`, `Offer_Received`,
or `Offer_Rejected` are considered terminal and do not trigger reminders.

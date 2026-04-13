# Known Bugs — Job Application Tracker

This page documents confirmed bugs, their impact, and the version/date each fix
was released.  Entries are listed newest-first.

Date format: **YYYYMMDD**

---

## How to read this page

| Field | Meaning |
|---|---|
| **ID** | Short reference code used in commits and issues |
| **Severity** | `Critical` · `High` · `Medium` · `Low` |
| **Affects** | Version(s) where the bug is present |
| **Fixed in** | Version that ships the fix (blank = not yet released) |
| **Fix date** | Date the fix was merged (`YYYYMMDD`) |

---

## Open bugs

_No known open bugs at this time._

> **Tip (v1.2.3+):** Admins can now inspect and edit the live database directly
> from the browser via **Settings → Database**.  This replaces the need for an
> external SQLite browser for most common debugging tasks.  See the
> [Admin Guide → Database Debug Viewer](admin-guide.md#8-database-debug-viewer)
> for SQL snippets and common fix recipes.

---

## Fixed bugs

### BUG-002 — Status list order is locked; users cannot reorder statuses

| | |
|---|---|
| **ID** | BUG-002 |
| **Severity** | Low |
| **Affects** | ≤ 1.2.0 |
| **Fixed in** | 1.2.1 |
| **Fix date** | 20260409 |

**Description**  
The custom-status list in **Settings → Statuses** displayed statuses in their
creation/database order with no way to change that order.  The `sort_order`
column in the `statuses` table existed but there was no UI or route to modify it.

**Symptoms**  
- Newly added statuses always appeared at the bottom of every dropdown, even
  when a different position was desired.
- The order shown in Settings was fixed; up/down controls were absent.

**Fix**  
Added `move_status(name, direction)` to `db/statuses.py`, exposed it via two new
POST actions (`move_status_up` / `move_status_down`) in
`routes/settings_routes.py`, and updated `templates/settings.html` to show ↑/↓
buttons in the status table.  The first status's ↑ button and the last status's
↓ button are disabled to prevent out-of-bounds moves.

**Workaround (before fix)**  
Manually update the `sort_order` column in the `statuses` table using an SQLite
browser (e.g. DB Browser for SQLite).

---

### BUG-001 — Company Pool setting causes Internal Server Error on company page

| | |
|---|---|
| **ID** | BUG-001 |
| **Severity** | Critical |
| **Affects** | ≤ 1.2.0 |
| **Fixed in** | 1.2.1 |
| **Fix date** | 20260409 |

**Description**  
Enabling **Settings → General → Company Pool** caused every visit to
`/companies` to crash with a Flask `BuildError` (HTTP 500 Internal Server
Error).  All other pages were unaffected.

**Symptoms**  
- HTTP 500 on `/companies` only when **Company Pool** is enabled.
- Flask traceback ending with:
  ```
  werkzeug.routing.exceptions.BuildError:
      Could not build url for endpoint 'settings'. ...
  ```
- Disabling the pool setting restored normal operation.

**Root cause**  
`templates/companies.html` contained an incorrect `url_for` call inside the
pool-info alert banner:

```html
<!-- broken -->
<a href="{{ url_for('settings', section='general') }}" …>Manage in Settings</a>

<!-- correct -->
<a href="{{ url_for('settings_routes.settings', section='general') }}" …>Manage in Settings</a>
```

Because the banner is only rendered when `pool_enabled` is `True`, the error
only appeared when the pool feature was active.

**Fix**  
Corrected the endpoint name in `templates/companies.html` line 25 from
`'settings'` to `'settings_routes.settings'`.

**Workaround (before fix)**  
Disable the Company Pool setting in **Settings → General** to prevent the
banner from rendering.

---

_To report a new bug, open a GitHub issue at
[MidnightMight/Job_Application_tracker](https://github.com/MidnightMight/Job_Application_tracker/issues)._

"""Public interface for the db package.

All symbols exported here were previously in ``database.py`` so existing
``import database as db; db.foo()`` call-sites continue to work via the
backward-compat shim in database.py.
"""

from .connection import (
    DB_PATH,
    YEARS,
    get_connection,
    get_dynamic_years,
    _add_column_if_missing,
    _BULK_UPDATE_FIELDS,
)

from .init_db import (
    DEFAULT_STATUSES,
    PENDING_STATUSES,
    init_db,
    clear_demo_data,
)

from .statuses import (
    PROTECTED_STATUSES,
    get_status_options,
    add_status,
    delete_status,
    move_status,
)

from .settings import (
    get_setting,
    set_setting,
    get_all_settings,
)

from .users import (
    get_users,
    count_users,
    add_user,
    delete_user,
    get_user_by_username,
)

from .reminders import (
    get_pending_for_reminders,
    create_reminder,
    get_reminders,
    dismiss_reminder,
    dismiss_all_reminders,
    get_unread_reminder_count,
)

from .stats import (
    get_stats,
    get_status_counts,
    get_apps_per_year,
    get_success_rate_per_year,
    get_company_note_frequency,
)

from .companies import (
    get_companies,
    get_company,
    add_company,
    update_company,
    delete_company,
    bulk_delete_companies,
)

from .applications import (
    get_applications,
    search_applications,
    get_application,
    get_application_timeline,
    add_application,
    update_application,
    delete_application,
    bulk_delete_applications,
    bulk_update_applications,
    find_duplicate_applications,
    bulk_import_applications,
    save_ai_fit,
)

__all__ = [
    # connection
    "DB_PATH", "YEARS", "get_connection", "get_dynamic_years",
    "_add_column_if_missing", "_BULK_UPDATE_FIELDS",
    # init_db
    "DEFAULT_STATUSES", "PENDING_STATUSES", "init_db", "clear_demo_data",
    # statuses
    "PROTECTED_STATUSES", "get_status_options", "add_status", "delete_status", "move_status",
    # settings
    "get_setting", "set_setting", "get_all_settings",
    # users
    "get_users", "count_users", "add_user", "delete_user", "get_user_by_username",
    # reminders
    "get_pending_for_reminders", "create_reminder", "get_reminders",
    "dismiss_reminder", "dismiss_all_reminders", "get_unread_reminder_count",
    # stats
    "get_stats", "get_status_counts", "get_apps_per_year",
    "get_success_rate_per_year", "get_company_note_frequency",
    # companies
    "get_companies", "get_company", "add_company", "update_company",
    "delete_company", "bulk_delete_companies",
    # applications
    "get_applications", "search_applications", "get_application",
    "get_application_timeline", "add_application", "update_application",
    "delete_application", "bulk_delete_applications", "bulk_update_applications",
    "find_duplicate_applications", "bulk_import_applications", "save_ai_fit",
]

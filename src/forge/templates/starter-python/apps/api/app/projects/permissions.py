"""The one place that says which role may do what with projects."""

from app.core import define_permissions

PROJECT_PERMISSIONS = define_permissions(
    "projects",
    {
        "admin": ["view", "create", "edit", "delete", "restore"],
        "member": ["view", "create", "edit"],
    },
)

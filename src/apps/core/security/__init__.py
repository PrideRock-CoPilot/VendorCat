"""Security module with RBAC decorators and utilities."""

from apps.core.security.rbac import require_all_permissions, require_any_permission, require_permission

__all__ = ["require_permission", "require_any_permission", "require_all_permissions"]

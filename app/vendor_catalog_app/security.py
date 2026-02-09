from __future__ import annotations


ROLE_ADMIN = "vendor_admin"
ROLE_STEWARD = "vendor_steward"
ROLE_EDITOR = "vendor_editor"
ROLE_VIEWER = "vendor_viewer"
ROLE_AUDITOR = "vendor_auditor"


def has_role(user_roles: set[str], role: str) -> bool:
    return role in user_roles


def can_edit(user_roles: set[str]) -> bool:
    return bool({ROLE_ADMIN, ROLE_EDITOR, ROLE_STEWARD}.intersection(user_roles))


def is_admin(user_roles: set[str]) -> bool:
    return ROLE_ADMIN in user_roles


def effective_roles(user_roles: set[str]) -> set[str]:
    if not user_roles:
        return {ROLE_VIEWER}
    return user_roles


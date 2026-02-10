from __future__ import annotations


ROLE_ADMIN = "vendor_admin"
ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_APPROVER = "vendor_approver"
ROLE_STEWARD = "vendor_steward"
ROLE_EDITOR = "vendor_editor"
ROLE_VIEWER = "vendor_viewer"
ROLE_AUDITOR = "vendor_auditor"
ROLE_CHOICES = (
    ROLE_SYSTEM_ADMIN,
    ROLE_ADMIN,
    ROLE_APPROVER,
    ROLE_STEWARD,
    ROLE_EDITOR,
    ROLE_VIEWER,
    ROLE_AUDITOR,
)
ADMIN_PORTAL_ROLES = (ROLE_SYSTEM_ADMIN, ROLE_ADMIN)

DEFAULT_APPROVAL_LEVEL = 2
APPROVAL_LEVEL_LABELS = {
    1: "level_1",
    2: "level_2",
    3: "level_3",
}

CHANGE_APPROVAL_LEVELS = {
    "create_vendor_profile": 3,
    "update_vendor_profile": 2,
    "update_offering": 2,
    "create_offering": 2,
    "map_contract_to_offering": 2,
    "map_demo_to_offering": 1,
    "add_vendor_owner": 2,
    "add_vendor_org_assignment": 2,
    "add_vendor_contact": 1,
    "add_offering_owner": 2,
    "remove_offering_owner": 2,
    "add_offering_contact": 1,
    "remove_offering_contact": 1,
    "update_offering_profile": 2,
    "add_offering_note": 1,
    "add_offering_ticket": 1,
    "update_offering_ticket": 1,
    "create_project": 2,
    "update_project": 2,
    "update_project_owner": 2,
    "attach_project_vendor": 2,
    "attach_project_offering": 2,
    "add_project_note": 1,
    "create_project_demo": 2,
    "update_project_demo": 1,
    "remove_project_demo": 1,
    "create_doc_link": 1,
    "remove_doc_link": 1,
    "create_demo_outcome": 2,
    "record_contract_cancellation": 3,
    "grant_role": 3,
    "grant_scope": 3,
}
CHANGE_ACTION_CHOICES = tuple(sorted(CHANGE_APPROVAL_LEVELS.keys()))

ROLE_DEFAULT_DEFINITIONS = {
    ROLE_SYSTEM_ADMIN: {
        "role_name": "System Admin",
        "description": "Platform administration access. Cannot edit vendor data or approve business changes.",
        "approval_level": 0,
        "can_edit": False,
        "can_report": True,
        "can_direct_apply": False,
    },
    ROLE_ADMIN: {
        "role_name": "Vendor Admin",
        "description": "Full administrative access across all workflows and data changes.",
        "approval_level": 3,
        "can_edit": True,
        "can_report": True,
        "can_direct_apply": True,
    },
    ROLE_APPROVER: {
        "role_name": "Vendor Approver",
        "description": "Can review and approve requests but cannot directly edit vendor records.",
        "approval_level": 2,
        "can_edit": False,
        "can_report": True,
        "can_direct_apply": False,
    },
    ROLE_STEWARD: {
        "role_name": "Vendor Steward",
        "description": "Data steward with elevated review/apply rights for governed updates.",
        "approval_level": 2,
        "can_edit": True,
        "can_report": True,
        "can_direct_apply": True,
    },
    ROLE_EDITOR: {
        "role_name": "Vendor Editor",
        "description": "Contributor role for day-to-day edits and change submissions.",
        "approval_level": 1,
        "can_edit": True,
        "can_report": True,
        "can_direct_apply": False,
    },
    ROLE_VIEWER: {
        "role_name": "Vendor Viewer",
        "description": "Read-only access to vendor inventory and metadata.",
        "approval_level": 0,
        "can_edit": False,
        "can_report": False,
        "can_direct_apply": False,
    },
    ROLE_AUDITOR: {
        "role_name": "Vendor Auditor",
        "description": "Read/report access for governance and audit functions.",
        "approval_level": 0,
        "can_edit": False,
        "can_report": True,
        "can_direct_apply": False,
    },
}


def has_role(user_roles: set[str], role: str) -> bool:
    return role in user_roles


def can_edit(user_roles: set[str]) -> bool:
    return bool({ROLE_ADMIN, ROLE_EDITOR, ROLE_STEWARD}.intersection(user_roles))


def is_admin(user_roles: set[str]) -> bool:
    return ROLE_ADMIN in user_roles


def has_admin_portal_access(user_roles: set[str]) -> bool:
    return bool(set(ADMIN_PORTAL_ROLES).intersection(user_roles))


def can_submit_change_requests(user_roles: set[str]) -> bool:
    if ROLE_SYSTEM_ADMIN in user_roles and not {ROLE_ADMIN, ROLE_STEWARD, ROLE_EDITOR}.intersection(user_roles):
        return False
    return bool({ROLE_ADMIN, ROLE_STEWARD, ROLE_EDITOR, ROLE_VIEWER}.intersection(user_roles))


def can_approve_requests(user_roles: set[str]) -> bool:
    if ROLE_SYSTEM_ADMIN in user_roles and not {ROLE_ADMIN, ROLE_STEWARD, ROLE_APPROVER}.intersection(user_roles):
        return False
    return bool({ROLE_ADMIN, ROLE_STEWARD, ROLE_APPROVER}.intersection(user_roles))


def effective_roles(user_roles: set[str]) -> set[str]:
    if not user_roles:
        return {ROLE_VIEWER}
    return user_roles


def approval_level_for_roles(user_roles: set[str]) -> int:
    level = 0
    if ROLE_EDITOR in user_roles:
        level = max(level, 1)
    if ROLE_STEWARD in user_roles or ROLE_APPROVER in user_roles:
        level = max(level, 2)
    if ROLE_ADMIN in user_roles:
        level = max(level, 3)
    return level


def required_approval_level(change_type: str) -> int:
    return CHANGE_APPROVAL_LEVELS.get((change_type or "").strip().lower(), DEFAULT_APPROVAL_LEVEL)


def approval_level_label(level: int) -> str:
    level = max(1, min(int(level or DEFAULT_APPROVAL_LEVEL), 3))
    return APPROVAL_LEVEL_LABELS.get(level, APPROVAL_LEVEL_LABELS[DEFAULT_APPROVAL_LEVEL])


def can_apply_change(user_roles: set[str], change_type: str) -> bool:
    return approval_level_for_roles(user_roles) >= required_approval_level(change_type)


def can_review_change(user_roles: set[str], required_level: int) -> bool:
    return approval_level_for_roles(user_roles) >= int(required_level or DEFAULT_APPROVAL_LEVEL)


def change_action_choices() -> tuple[str, ...]:
    return CHANGE_ACTION_CHOICES


def default_role_definitions() -> dict[str, dict[str, object]]:
    return {key: dict(value) for key, value in ROLE_DEFAULT_DEFINITIONS.items()}


def default_change_permissions_for_role(role_code: str) -> set[str]:
    role = str(role_code or "").strip().lower()
    if role == ROLE_ADMIN:
        return set(CHANGE_APPROVAL_LEVELS.keys())
    level = int(ROLE_DEFAULT_DEFINITIONS.get(role, {}).get("approval_level", 0))
    return {
        action
        for action, required in CHANGE_APPROVAL_LEVELS.items()
        if int(required) <= level
    }

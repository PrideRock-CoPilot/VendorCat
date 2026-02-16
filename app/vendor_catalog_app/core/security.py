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

MIN_APPROVAL_LEVEL = 0
MAX_APPROVAL_LEVEL = 10
MIN_CHANGE_APPROVAL_LEVEL = 1
DEFAULT_APPROVAL_LEVEL = 6

CHANGE_APPROVAL_LEVELS = {
    "request_access": 3,
    "create_vendor_profile": 9,
    "update_vendor_profile": 6,
    "update_offering": 6,
    "create_offering": 6,
    "create_contract": 6,
    "update_contract": 6,
    "map_contract_to_offering": 6,
    "map_demo_to_offering": 3,
    "add_vendor_owner": 6,
    "add_vendor_org_assignment": 6,
    "add_vendor_contact": 3,
    "add_offering_owner": 6,
    "remove_offering_owner": 6,
    "add_offering_contact": 3,
    "remove_offering_contact": 3,
    "update_offering_profile": 6,
    "add_offering_note": 3,
    "add_offering_ticket": 3,
    "update_offering_ticket": 3,
    "add_offering_invoice": 3,
    "remove_offering_invoice": 3,
    "create_project": 6,
    "update_project": 6,
    "update_project_owner": 6,
    "attach_project_vendor": 6,
    "attach_project_offering": 6,
    "add_project_note": 3,
    "create_project_demo": 6,
    "update_project_demo": 3,
    "remove_project_demo": 3,
    "create_doc_link": 3,
    "remove_doc_link": 3,
    "create_demo_outcome": 6,
    "record_contract_cancellation": 9,
    "grant_role": 9,
    "grant_scope": 9,
}
CHANGE_ACTION_CHOICES = tuple(sorted(CHANGE_APPROVAL_LEVELS.keys()))
ACCESS_REQUEST_ALLOWED_ROLES = (
    ROLE_VIEWER,
    ROLE_EDITOR,
    ROLE_AUDITOR,
)

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
        "approval_level": 10,
        "can_edit": True,
        "can_report": True,
        "can_direct_apply": True,
    },
    ROLE_APPROVER: {
        "role_name": "Vendor Approver",
        "description": "Can review and approve requests but cannot directly edit vendor records.",
        "approval_level": 7,
        "can_edit": False,
        "can_report": True,
        "can_direct_apply": False,
    },
    ROLE_STEWARD: {
        "role_name": "Vendor Steward",
        "description": "Data steward with elevated review/apply rights for governed updates.",
        "approval_level": 7,
        "can_edit": True,
        "can_report": True,
        "can_direct_apply": True,
    },
    ROLE_EDITOR: {
        "role_name": "Vendor Editor",
        "description": "Contributor role for day-to-day edits and change submissions.",
        "approval_level": 4,
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
    level = MIN_APPROVAL_LEVEL
    for role_code in user_roles:
        role_level = int(ROLE_DEFAULT_DEFINITIONS.get(str(role_code), {}).get("approval_level", MIN_APPROVAL_LEVEL))
        level = max(level, role_level)
    return max(MIN_APPROVAL_LEVEL, min(level, MAX_APPROVAL_LEVEL))


def required_approval_level(change_type: str) -> int:
    return CHANGE_APPROVAL_LEVELS.get((change_type or "").strip().lower(), DEFAULT_APPROVAL_LEVEL)


def approval_level_label(level: int) -> str:
    level = max(MIN_CHANGE_APPROVAL_LEVEL, min(int(level or DEFAULT_APPROVAL_LEVEL), MAX_APPROVAL_LEVEL))
    return f"level_{level}"


def can_apply_change(user_roles: set[str], change_type: str) -> bool:
    return approval_level_for_roles(user_roles) >= required_approval_level(change_type)


def can_review_change(user_roles: set[str], required_level: int) -> bool:
    level = max(MIN_CHANGE_APPROVAL_LEVEL, min(int(required_level or DEFAULT_APPROVAL_LEVEL), MAX_APPROVAL_LEVEL))
    return approval_level_for_roles(user_roles) >= level


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

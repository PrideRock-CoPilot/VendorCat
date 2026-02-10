from __future__ import annotations

from dataclasses import dataclass

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.security import (
    ADMIN_PORTAL_ROLES,
    ROLE_ADMIN,
    CHANGE_APPROVAL_LEVELS,
    can_approve_requests,
    required_approval_level,
    can_apply_change,
    can_review_change,
    can_submit_change_requests,
    approval_level_for_roles,
)


@dataclass(frozen=True)
class UserContext:
    user_principal: str
    roles: set[str]
    raw_roles: set[str]
    config: AppConfig
    role_override: str | None = None
    role_policy: dict[str, object] | None = None

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles

    @property
    def has_admin_rights(self) -> bool:
        return bool(set(ADMIN_PORTAL_ROLES).intersection(self.raw_roles))

    @property
    def can_edit(self) -> bool:
        if self.role_policy is not None and "can_edit" in self.role_policy:
            return bool(self.role_policy.get("can_edit"))
        return bool({"vendor_admin", "vendor_editor", "vendor_steward"}.intersection(self.roles))

    @property
    def can_report(self) -> bool:
        if self.role_policy is not None and "can_report" in self.role_policy:
            return bool(self.role_policy.get("can_report"))
        return bool({"vendor_admin", "vendor_editor", "vendor_steward", "vendor_auditor"}.intersection(self.roles))

    @property
    def can_submit_requests(self) -> bool:
        if self.role_policy is not None and "can_submit_requests" in self.role_policy:
            return bool(self.role_policy.get("can_submit_requests"))
        return can_submit_change_requests(self.roles)

    @property
    def can_approve_requests(self) -> bool:
        if self.role_policy is not None and "can_approve_requests" in self.role_policy:
            return bool(self.role_policy.get("can_approve_requests"))
        return can_approve_requests(self.roles)

    @property
    def can_access_workflows(self) -> bool:
        return self.can_edit or self.can_submit_requests or self.can_approve_requests

    @property
    def can_direct_apply(self) -> bool:
        if self.role_policy is not None and "can_direct_apply" in self.role_policy:
            return bool(self.role_policy.get("can_direct_apply"))
        return bool({"vendor_admin", "vendor_steward"}.intersection(self.roles))

    @property
    def approval_level(self) -> int:
        if self.role_policy is not None and "approval_level" in self.role_policy:
            try:
                return int(self.role_policy.get("approval_level") or 0)
            except Exception:
                return 0
        return approval_level_for_roles(self.roles)

    def can_apply_change(self, change_type: str) -> bool:
        if self.role_policy is not None:
            allowed_raw = self.role_policy.get("allowed_change_actions", [])
            allowed_actions = {
                str(item).strip().lower()
                for item in (allowed_raw or [])
                if str(item).strip()
            }
            target = str(change_type or "").strip().lower()
            if target in CHANGE_APPROVAL_LEVELS and target not in allowed_actions:
                return False
            return self.approval_level >= required_approval_level(target)
        return can_apply_change(self.roles, change_type)

    def can_review_level(self, required_level: int) -> bool:
        if not self.can_approve_requests:
            return False
        if self.role_policy is not None:
            return self.approval_level >= int(required_level or 0)
        return can_review_change(self.roles, required_level)

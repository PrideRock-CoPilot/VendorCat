from __future__ import annotations

from dataclasses import dataclass

from vendor_catalog_app.config import AppConfig


@dataclass(frozen=True)
class UserContext:
    user_principal: str
    roles: set[str]
    config: AppConfig

    @property
    def is_admin(self) -> bool:
        return "vendor_admin" in self.roles

    @property
    def can_edit(self) -> bool:
        return bool({"vendor_admin", "vendor_editor", "vendor_steward"}.intersection(self.roles))

    @property
    def can_report(self) -> bool:
        return bool({"vendor_admin", "vendor_editor", "vendor_steward", "vendor_auditor"}.intersection(self.roles))

    @property
    def can_direct_apply(self) -> bool:
        return bool({"vendor_admin", "vendor_steward"}.intersection(self.roles))

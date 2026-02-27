from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    permission: str
    reason: str


@dataclass(frozen=True)
class PolicySnapshot:
    user_principal: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]

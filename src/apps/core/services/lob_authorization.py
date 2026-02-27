from __future__ import annotations

from apps.core.contracts.policy import PolicySnapshot
from apps.core.services.policy_engine import PolicyEngine

_SCOPE_RANK = {
    "view": 1,
    "read": 1,
    "edit": 2,
    "write": 2,
    "admin": 3,
}


def _scope_entries(snapshot: PolicySnapshot) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for item in snapshot.scopes:
        raw = str(item or "").strip()
        if ":" not in raw:
            continue
        org_id, level = raw.rsplit(":", 1)
        org = org_id.strip().lower()
        lvl = level.strip().lower()
        if not org or not lvl:
            continue
        entries.append((org, lvl))
    return entries


def is_scope_restricted(snapshot: PolicySnapshot) -> bool:
    return len(_scope_entries(snapshot)) > 0


def has_lob_scope(snapshot: PolicySnapshot, lob: str, *, minimum_level: str = "view") -> bool:
    target = str(lob or "").strip().lower()
    if not target:
        return True

    required_rank = _SCOPE_RANK.get(str(minimum_level or "view").strip().lower(), 1)
    for org_id, level in _scope_entries(snapshot):
        if org_id not in {target, "*", "all"}:
            continue
        if _SCOPE_RANK.get(level, 0) >= required_rank:
            return True
    return False


def has_vendor_level_scope(
    snapshot: PolicySnapshot,
    *,
    owner_org_id: str,
    offering_lobs: list[str] | tuple[str, ...],
    minimum_level: str = "edit",
) -> bool:
    lob_values = {str(owner_org_id or "").strip().lower()}
    lob_values.update(str(value or "").strip().lower() for value in offering_lobs)
    lob_values = {value for value in lob_values if value}
    if not lob_values:
        return True
    return all(has_lob_scope(snapshot, lob, minimum_level=minimum_level) for lob in lob_values)


def can_view_contracts(snapshot: PolicySnapshot) -> bool:
    return PolicyEngine.decide(snapshot, "contract.read").allowed or PolicyEngine.decide(
        snapshot,
        "contract.write",
    ).allowed

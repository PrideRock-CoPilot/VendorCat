from __future__ import annotations

from apps.core.services.permission_registry import MUTATION_PERMISSION_MAP


def test_mutation_contract_map_is_explicit() -> None:
    assert MUTATION_PERMISSION_MAP
    for (method, path), permission in MUTATION_PERMISSION_MAP.items():
        assert method in {"POST", "PUT", "PATCH", "DELETE"}
        assert path.startswith("/api/v1/")
        assert permission and permission != "*"

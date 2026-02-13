from __future__ import annotations

from datetime import datetime, timezone

from vendor_catalog_app.repository import SchemaBootstrapRequiredError

def _normalize_limit(limit: int) -> int:
    return max(1, min(int(limit or 20), 50))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_ready(repo) -> tuple[bool, str | None]:
    try:
        repo.ensure_runtime_tables()
        return True, None
    except SchemaBootstrapRequiredError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, f"Connection check failed: {exc}"

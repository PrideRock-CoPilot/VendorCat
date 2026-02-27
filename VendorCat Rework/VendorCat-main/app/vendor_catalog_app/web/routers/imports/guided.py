from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from vendor_catalog_app.core.env import (
    TVENDOR_IMPORTS_GUIDED_UX_V3,
    get_env_bool,
)

IMPORTS_TOUR_SETTING_KEY = "imports.guided_tour.v2"
IMPORTS_TOUR_VERSION = "v2"

IMPORTS_GUIDED_EVENTS = {
    "imports_guided_step_view",
    "imports_guided_low_confidence_continue",
    "imports_guided_expert_mode_opened",
    "imports_guided_apply_confirmed",
}


def imports_guided_enabled(config) -> bool:
    default_enabled = bool(getattr(config, "is_dev_env", True))
    return get_env_bool(TVENDOR_IMPORTS_GUIDED_UX_V3, default=default_enabled)


def show_imports_guided_tour(
    repo,
    *,
    user_principal: str,
    guided_enabled: bool,
) -> bool:
    if not guided_enabled:
        return False
    try:
        payload = dict(repo.get_user_setting(user_principal, IMPORTS_TOUR_SETTING_KEY) or {})
    except Exception:
        payload = {}
    dismissed = bool(payload.get("dismissed", False))
    version = str(payload.get("version") or "").strip() or IMPORTS_TOUR_VERSION
    return not (dismissed and version == IMPORTS_TOUR_VERSION)


def dismiss_imports_guided_tour(
    repo,
    *,
    user_principal: str,
) -> None:
    payload = {
        "dismissed": True,
        "dismissed_at": datetime.now(UTC).isoformat(),
        "version": IMPORTS_TOUR_VERSION,
    }
    repo.save_user_setting(user_principal, IMPORTS_TOUR_SETTING_KEY, payload)


def log_imports_guided_event(
    repo,
    *,
    user_principal: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    event_name = str(event_type or "").strip()
    if event_name not in IMPORTS_GUIDED_EVENTS:
        return
    if not hasattr(repo, "log_usage_event"):
        return
    try:
        repo.log_usage_event(
            user_principal=user_principal,
            page_name="imports_guided",
            event_type=event_name,
            payload=dict(payload or {}),
        )
    except Exception:
        return

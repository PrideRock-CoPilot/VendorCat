from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from vendor_catalog_app.core.env import (
    TVENDOR_MERGE_CENTER_GUIDED_UX_V2,
    get_env_bool,
)

MERGE_CENTER_TOUR_SETTING_KEY = "vendors.merge_center_tour.v2"
MERGE_CENTER_TOUR_VERSION = "v2"

MERGE_CENTER_GUIDED_EVENTS = {
    "merge_center_step_view",
    "merge_center_execute_confirmed",
}


def merge_center_guided_enabled(config) -> bool:
    default_enabled = bool(getattr(config, "is_dev_env", True))
    return get_env_bool(TVENDOR_MERGE_CENTER_GUIDED_UX_V2, default=default_enabled)


def show_merge_center_guided_tour(
    repo,
    *,
    user_principal: str,
    guided_enabled: bool,
) -> bool:
    if not guided_enabled:
        return False
    try:
        payload = dict(repo.get_user_setting(user_principal, MERGE_CENTER_TOUR_SETTING_KEY) or {})
    except Exception:
        payload = {}
    dismissed = bool(payload.get("dismissed", False))
    version = str(payload.get("version") or "").strip() or MERGE_CENTER_TOUR_VERSION
    return not (dismissed and version == MERGE_CENTER_TOUR_VERSION)


def dismiss_merge_center_guided_tour(
    repo,
    *,
    user_principal: str,
) -> None:
    payload = {
        "dismissed": True,
        "dismissed_at": datetime.now(UTC).isoformat(),
        "version": MERGE_CENTER_TOUR_VERSION,
    }
    repo.save_user_setting(user_principal, MERGE_CENTER_TOUR_SETTING_KEY, payload)


def log_merge_center_guided_event(
    repo,
    *,
    user_principal: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    event_name = str(event_type or "").strip()
    if event_name not in MERGE_CENTER_GUIDED_EVENTS:
        return
    if not hasattr(repo, "log_usage_event"):
        return
    try:
        repo.log_usage_event(
            user_principal=user_principal,
            page_name="vendor_merge_center",
            event_type=event_name,
            payload=dict(payload or {}),
        )
    except Exception:
        return

from __future__ import annotations

from fastapi import Request

from vendor_catalog_app.web.core.context import UserContext
from vendor_catalog_app.web.core.runtime import get_repo


def ensure_session_started(request: Request, context: UserContext) -> None:
    repo = get_repo()
    session_key = f"usage_session_started_for_{context.user_principal}"
    if request.session.get(session_key):
        return

    repo.log_usage_event(
        user_principal=context.user_principal,
        page_name="app",
        event_type="session_start",
        payload={"locked_mode": context.config.locked_mode},
    )
    request.session[session_key] = True


def log_page_view(request: Request, context: UserContext, page_name: str) -> None:
    repo = get_repo()
    session_key = f"usage_last_page_for_{context.user_principal}"
    if request.session.get(session_key) == page_name:
        return
    repo.log_usage_event(
        user_principal=context.user_principal,
        page_name=page_name,
        event_type="page_view",
        payload=None,
    )
    request.session[session_key] = page_name

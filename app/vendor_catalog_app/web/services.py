from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import Request

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.repository import VendorRepository
from vendor_catalog_app.security import effective_roles
from vendor_catalog_app.web.context import UserContext
from vendor_catalog_app.web.flash import pop_flashes


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig.from_env()


@lru_cache(maxsize=1)
def get_repo() -> VendorRepository:
    return VendorRepository(get_config())


def _resolve_user_principal(repo: VendorRepository, config: AppConfig, request: Request) -> str:
    forced_user = request.query_params.get("as_user")
    if config.use_mock and forced_user:
        return forced_user
    if config.use_mock:
        return os.getenv("TVENDOR_TEST_USER", "admin@example.com")
    return repo.get_current_user()


def get_user_context(request: Request) -> UserContext:
    cached = getattr(request.state, "user_context", None)
    if cached is not None:
        return cached

    repo = get_repo()
    config = get_config()
    repo.ensure_runtime_tables()

    user_principal = _resolve_user_principal(repo, config, request)
    roles = effective_roles(repo.bootstrap_user_access(user_principal))
    context = UserContext(user_principal=user_principal, roles=roles, config=config)
    request.state.user_context = context
    return context


def ensure_session_started(request: Request, context: UserContext) -> None:
    repo = get_repo()
    session_key = f"usage_session_started_for_{context.user_principal}"
    if request.session.get(session_key):
        return

    repo.log_usage_event(
        user_principal=context.user_principal,
        page_name="app",
        event_type="session_start",
        payload={"locked_mode": context.config.locked_mode, "use_mock": context.config.use_mock},
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


def base_template_context(
    request: Request,
    context: UserContext,
    title: str,
    active_nav: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request": request,
        "title": title,
        "active_nav": active_nav,
        "user_principal": context.user_principal,
        "roles": sorted(list(context.roles)),
        "can_edit": context.can_edit,
        "can_report": context.can_report,
        "can_direct_apply": context.can_direct_apply,
        "is_admin": context.is_admin,
        "fq_schema": context.config.fq_schema,
        "use_mock": context.config.use_mock,
        "use_local_db": context.config.use_local_db,
        "local_db_path": context.config.local_db_path,
        "locked_mode": context.config.locked_mode,
        "flashes": pop_flashes(request),
    }
    if extra:
        payload.update(extra)
    return payload

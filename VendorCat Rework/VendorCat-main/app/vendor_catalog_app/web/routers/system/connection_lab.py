from __future__ import annotations

import logging
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import (
    activate_request_runtime_override,
    deactivate_request_runtime_override,
    get_config,
    get_repo,
)
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash, pop_flashes
from vendor_catalog_app.web.system.bootstrap_diagnostics import build_bootstrap_diagnostics_payload
from vendor_catalog_app.web.system.connection_lab import (
    authorize_connection_lab,
    build_override_from_form,
    clear_runtime_override_for_session,
    connection_lab_authorized,
    connection_lab_enabled,
    load_runtime_override_from_session,
    override_preview,
    save_runtime_override_for_session,
)

router = APIRouter()
LOGGER = logging.getLogger(__name__)


def _safe_next_path(raw_next: str) -> str:
    decoded = unquote(str(raw_next or "").strip())
    if not decoded:
        return "/dashboard"
    if not decoded.startswith("/") or decoded.startswith("//"):
        return "/dashboard"
    return decoded


def _clear_user_context_session_cache(session: dict) -> None:
    for key in list(session.keys()):
        if str(key).startswith("tvendor_identity_synced_at:"):
            session.pop(key, None)
        if str(key).startswith("tvendor_policy_snapshot:"):
            session.pop(key, None)
    session.pop("tvendor_admin_role_override", None)


def _check_permission_connection_lab(request: Request) -> bool:
    user = get_user_context(request)
    active_roles = set(getattr(user, "roles", set()) or set())
    if not active_roles:
        return True
    # Keep connection-lab flow permissive while still exercising explicit RBAC checks.
    return user.can_apply_change("feedback_submit")


def _render_connection_lab_page(
    request: Request,
    *,
    probe_payload: dict | None = None,
    probe_status_code: int = 200,
    form_state: dict | None = None,
) -> object:
    config = get_config()
    if not connection_lab_enabled(config):
        return PlainTextResponse("Not found.", status_code=404)

    authorized = connection_lab_authorized(request, config)
    session = request.scope.get("session")
    active_override = load_runtime_override_from_session(session if isinstance(session, dict) else None)
    active_override_preview = override_preview(active_override)
    current_config = get_config()
    defaults = {
        "databricks_server_hostname": str(current_config.databricks_server_hostname or "").strip(),
        "databricks_http_path": str(current_config.databricks_http_path or "").strip(),
        "databricks_warehouse_id": "",
        "auth_mode": "inherit",
    }
    defaults.update(dict(form_state or {}))

    context = {
        "request": request,
        "csrf_token": str(getattr(request.state, "csrf_token", "") or ""),
        "authorized": authorized,
        "active_override_preview": active_override_preview,
        "probe_payload": probe_payload,
        "probe_status_code": int(probe_status_code),
        "flashes": pop_flashes(request),
        "form_state": defaults,
        "return_to": _safe_next_path(str(request.query_params.get("next", "/dashboard"))),
    }
    status_code = int(probe_status_code if probe_payload is not None else 200)
    return request.app.state.templates.TemplateResponse(
        request,
        "connection_lab.html",
        context,
        status_code=status_code,
    )


@router.get("/connection-lab")
def connection_lab_page(request: Request):
    return _render_connection_lab_page(request)


@router.post("/connection-lab/authorize")
async def connection_lab_authorize(request: Request):
    config = get_config()
    if not connection_lab_enabled(config):
        return PlainTextResponse("Not found.", status_code=404)
    if not _check_permission_connection_lab(request):
        add_flash(request, "You do not have permission to use connection lab.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    form = await request.form()
    next_path = _safe_next_path(str(form.get("next", "/connection-lab") or "/connection-lab"))
    provided_token = str(form.get("connection_lab_token", "") or "")
    if authorize_connection_lab(request, provided_token):
        add_flash(request, "Connection lab unlocked for this browser session.", "success")
    else:
        add_flash(request, "Invalid connection lab token.", "error")
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/connection-lab/clear")
async def connection_lab_clear(request: Request):
    config = get_config()
    if not connection_lab_enabled(config):
        return PlainTextResponse("Not found.", status_code=404)
    if not _check_permission_connection_lab(request):
        add_flash(request, "You do not have permission to use connection lab.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    form = await request.form()
    next_path = _safe_next_path(str(form.get("next", "/connection-lab") or "/connection-lab"))
    clear_runtime_override_for_session(request)
    session = request.scope.get("session")
    if isinstance(session, dict):
        _clear_user_context_session_cache(session)
    add_flash(request, "Temporary connection override cleared.", "info")
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/connection-lab/apply")
async def connection_lab_apply(request: Request):
    config = get_config()
    if not connection_lab_enabled(config):
        return PlainTextResponse("Not found.", status_code=404)
    if not _check_permission_connection_lab(request):
        add_flash(request, "You do not have permission to use connection lab.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if not connection_lab_authorized(request, config):
        add_flash(request, "Connection lab is locked. Enter the secret token first.", "error")
        return RedirectResponse(url="/connection-lab", status_code=303)

    form = await request.form()
    next_path = _safe_next_path(str(form.get("next", "/dashboard") or "/dashboard"))
    override = build_override_from_form(dict(form))
    if not override:
        add_flash(
            request,
            "No override values supplied. Provide host/path and optional credentials.",
            "error",
        )
        return RedirectResponse(url="/connection-lab", status_code=303)
    if not save_runtime_override_for_session(request, override):
        add_flash(request, "Could not save runtime override for this session.", "error")
        return RedirectResponse(url="/connection-lab", status_code=303)

    session = request.scope.get("session")
    if isinstance(session, dict):
        _clear_user_context_session_cache(session)
    add_flash(request, "Temporary connection override saved for this browser session.", "success")
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/connection-lab/probe")
async def connection_lab_probe(request: Request):
    config = get_config()
    if not connection_lab_enabled(config):
        return PlainTextResponse("Not found.", status_code=404)
    if not _check_permission_connection_lab(request):
        add_flash(request, "You do not have permission to use connection lab.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if not connection_lab_authorized(request, config):
        add_flash(request, "Connection lab is locked. Enter the secret token first.", "error")
        return RedirectResponse(url="/connection-lab", status_code=303)

    form = await request.form()
    override = build_override_from_form(dict(form))
    form_state = {
        "databricks_server_hostname": str(form.get("databricks_server_hostname", "") or "").strip(),
        "databricks_http_path": str(form.get("databricks_http_path", "") or "").strip(),
        "databricks_warehouse_id": str(form.get("databricks_warehouse_id", "") or "").strip(),
        "auth_mode": str(form.get("auth_mode", "inherit") or "inherit").strip().lower() or "inherit",
    }
    override_tokens = activate_request_runtime_override(override)
    try:
        repo = get_repo()
        override_config = get_config()
        identity = resolve_databricks_request_identity(request)
        payload, status_code = build_bootstrap_diagnostics_payload(repo, override_config, identity)
        payload["connection_lab"] = {
            "override_applied": bool(override),
            "override_preview": override_preview(override),
        }
        return _render_connection_lab_page(
            request,
            probe_payload=payload,
            probe_status_code=status_code,
            form_state=form_state,
        )
    except Exception:
        LOGGER.warning("Connection lab probe failed.", exc_info=True)
        payload = {
            "ok": False,
            "mode": "databricks",
            "schema": str(get_config().fq_schema),
            "checks": [],
            "recommendations": [
                "Probe failed before diagnostics could complete. Check host/path/auth values and retry."
            ],
            "connection_lab": {
                "override_applied": bool(override),
                "override_preview": override_preview(override),
            },
        }
        return _render_connection_lab_page(
            request,
            probe_payload=payload,
            probe_status_code=503,
            form_state=form_state,
        )
    finally:
        deactivate_request_runtime_override(override_tokens)

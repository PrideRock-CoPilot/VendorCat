from __future__ import annotations

import logging
from urllib.parse import quote, unquote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.repository_constants import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.core.security import ACCESS_REQUEST_ALLOWED_ROLES
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.terms import (
    has_current_terms_acceptance,
    record_terms_acceptance,
    terms_document,
    terms_enforcement_enabled,
)
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash

router = APIRouter(prefix="/access")
LOGGER = logging.getLogger(__name__)
TERMINAL_ACCESS_REQUEST_STATUSES = {"approved", "rejected"}


def _safe_next_path(raw_next: str) -> str:
    decoded = unquote(str(raw_next or "").strip())
    if not decoded:
        return "/dashboard"
    if not decoded.startswith("/") or decoded.startswith("//"):
        return "/dashboard"
    if decoded.startswith("/access/terms"):
        return "/dashboard"
    return decoded


def _allowed_role_options(repo) -> list[str]:
    allowed = set(ACCESS_REQUEST_ALLOWED_ROLES)
    known = [str(role).strip() for role in repo.list_known_roles() if str(role).strip()]
    out = [role for role in known if role in allowed]
    if out:
        return out
    return list(ACCESS_REQUEST_ALLOWED_ROLES)


def _status_code(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    return cleaned or "submitted"


def _user_principal_refs(repo, user_principal: str) -> set[str]:
    refs: set[str] = set()
    principal = str(user_principal or "").strip()
    if not principal:
        return refs
    refs.add(principal.lower())
    try:
        login_identifier = str(repo.resolve_user_login_identifier(principal) or "").strip().lower()
        if login_identifier:
            refs.add(login_identifier)
    except Exception:
        LOGGER.debug("Could not resolve login identifier for '%s'.", principal, exc_info=True)
    try:
        actor_ref = str(repo._actor_ref(principal) or "").strip().lower()
        if actor_ref:
            refs.add(actor_ref)
    except Exception:
        LOGGER.debug("Could not resolve actor reference for '%s'.", principal, exc_info=True)
    return {ref for ref in refs if ref}


def _request_belongs_to_user(row: dict, user_refs: set[str]) -> bool:
    if not user_refs:
        return False
    requestor_ref = str(
        row.get("requestor_user_principal_raw")
        or row.get("requestor_user_principal")
        or ""
    ).strip().lower()
    return requestor_ref in user_refs


def _load_access_requests(
    repo,
    *,
    requestor_user_principal: str,
    limit: int = 20,
) -> list[dict]:
    user_principal = str(requestor_user_principal or "").strip()
    if not user_principal or user_principal == UNKNOWN_USER_PRINCIPAL:
        return []
    user_refs = _user_principal_refs(repo, user_principal)
    if not user_refs:
        return []

    safe_limit = max(1, min(int(limit or 20), 100))
    rows: list[dict] = []

    # Compatibility path if a filtered helper exists on the repository.
    list_vendor_change_requests = getattr(repo, "list_vendor_change_requests", None)
    if callable(list_vendor_change_requests):
        raw_rows = list_vendor_change_requests(
            change_type="request_access",
            requestor_user_principal=user_principal,
            status_filter="all",
            limit=safe_limit,
        )
        if hasattr(raw_rows, "to_dict"):
            rows = list(raw_rows.to_dict("records"))
        elif isinstance(raw_rows, list):
            rows = [dict(item) for item in raw_rows if isinstance(item, dict)]
    else:
        rows = repo.list_change_requests(status="all").to_dict("records")

    out: list[dict] = []
    for row in rows:
        if str(row.get("change_type") or "").strip().lower() != "request_access":
            continue
        if not _request_belongs_to_user(row, user_refs):
            continue
        status = _status_code(str(row.get("status") or ""))
        normalized = dict(row)
        normalized["status_code"] = status
        normalized["status_label"] = status.replace("_", " ").title()
        normalized["is_open"] = status not in TERMINAL_ACCESS_REQUEST_STATUSES
        normalized["submitted_at"] = row.get("submitted_at")
        normalized["last_updated_at"] = row.get("updated_at") or row.get("submitted_at")
        out.append(normalized)

    out.sort(
        key=lambda item: (
            str(item.get("submitted_at") or ""),
            str(item.get("last_updated_at") or ""),
        ),
        reverse=True,
    )
    return out[:safe_limit]


def _has_open_access_request(repo, *, requestor_user_principal: str) -> bool:
    rows = _load_access_requests(
        repo,
        requestor_user_principal=requestor_user_principal,
        limit=50,
    )
    return any(bool(row.get("is_open")) for row in rows)


@router.get("/request")
def access_request_page(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    forwarded_identity = resolve_databricks_request_identity(request)
    user_principal = str(getattr(user, "user_principal", "") or "").strip() or UNKNOWN_USER_PRINCIPAL
    identity_is_valid = user_principal != UNKNOWN_USER_PRINCIPAL
    ensure_session_started(request, user)
    log_page_view(request, user, "Request Access")
    requested_role_options = _allowed_role_options(repo)

    # Fetch access requests for this user.
    access_requests: list[dict] = []
    open_requests: list[dict] = []
    if identity_is_valid:
        try:
            access_requests = _load_access_requests(
                repo,
                requestor_user_principal=user_principal,
                limit=20,
            )
            open_requests = [row for row in access_requests if bool(row.get("is_open"))]
        except Exception:
            LOGGER.warning(
                "Could not load access request status for user '%s'.",
                user_principal,
                exc_info=True,
            )
            access_requests = []
            open_requests = []

    context = base_template_context(
        request=request,
        context=user,
        title="Request Access",
        active_nav="request_access",
        extra={
            "requested_role_options": requested_role_options,
            "selected_role": requested_role_options[0] if requested_role_options else "",
            "identity_is_valid": identity_is_valid,
            "identity_email": str(forwarded_identity.get("email") or "").strip(),
            "identity_network_id": str(forwarded_identity.get("network_id") or "").strip(),
            "identity_note": (
                "Requests will be submitted under this identity."
                if identity_is_valid
                else (
                    "No trusted principal was detected. In local dev, set TVENDOR_TEST_USER. "
                    "In Databricks Apps, verify forwarded identity headers are available."
                )
            ),
            "access_requests": access_requests,
            "open_requests": open_requests,
            "open_request_exists": bool(open_requests),
            # Temporary compatibility with older templates.
            "pending_requests": open_requests,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "access_request.html", context)


@router.post("/request")
async def submit_access_request(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    requested_role = str(form.get("requested_role", "")).strip().lower()
    justification = str(form.get("justification", "")).strip()

    if user.user_principal == UNKNOWN_USER_PRINCIPAL:
        detected_principal = str(getattr(user, "user_principal", "") or "").strip() or UNKNOWN_USER_PRINCIPAL
        add_flash(
            request,
            (
                "A valid user identity is required before requesting access. "
                f"Detected principal: {detected_principal}."
            ),
            "error",
        )
        return RedirectResponse(url="/access/request", status_code=303)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Access requests are disabled.", "error")
        return RedirectResponse(url="/access/request", status_code=303)
    try:
        if _has_open_access_request(repo, requestor_user_principal=user.user_principal):
            add_flash(
                request,
                "An access request is already open for your account. Wait for a decision before submitting another request.",
                "info",
            )
            return RedirectResponse(url="/access/request", status_code=303)
    except Exception:
        LOGGER.warning(
            "Could not verify open access requests for '%s'.",
            user.user_principal,
            exc_info=True,
        )
        add_flash(
            request,
            "Could not verify existing access requests right now. Please try again.",
            "error",
        )
        return RedirectResponse(url="/access/request", status_code=303)

    allowed_roles = set(_allowed_role_options(repo))
    if requested_role not in allowed_roles:
        add_flash(request, "Requested role must be selected from the approved list.", "error")
        return RedirectResponse(url="/access/request", status_code=303)
    if not justification:
        add_flash(request, "Justification is required.", "error")
        return RedirectResponse(url="/access/request", status_code=303)

    try:
        request_id = repo.create_access_request(
            requestor_user_principal=user.user_principal,
            requested_role=requested_role,
            justification=justification,
        )
        add_flash(request, f"Access request submitted: {request_id}", "success")
        return RedirectResponse(url="/access/request", status_code=303)
    except Exception as exc:
        add_flash(request, f"Could not submit access request: {exc}", "error")
        return RedirectResponse(url="/access/request", status_code=303)


@router.get("/terms")
def access_terms_page(request: Request, next: str = "/dashboard"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Terms Of Use")
    if not terms_enforcement_enabled():
        return RedirectResponse(url=_safe_next_path(next), status_code=303)

    next_path = _safe_next_path(next)
    if has_current_terms_acceptance(
        request=request,
        repo=repo,
        user_principal=user.user_principal,
    ):
        return RedirectResponse(url=next_path, status_code=303)

    context = base_template_context(
        request=request,
        context=user,
        title="Terms Of Use",
        active_nav="",
        extra={
            "next_path": next_path,
            "terms": terms_document(repo=repo),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "access_terms.html", context)


@router.get("/terms/view")
def access_terms_view_page(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Terms Of Use View")
    context = base_template_context(
        request=request,
        context=user,
        title="User Agreement",
        active_nav="",
        extra={
            "terms": terms_document(repo=repo),
            "show_accept": False,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "access_terms.html", context)


@router.post("/terms/accept")
async def accept_terms(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    if not terms_enforcement_enabled():
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    next_path = _safe_next_path(str(form.get("next", "/dashboard") or "/dashboard"))
    agree = str(form.get("agree_terms", "")).strip().lower() in {"1", "true", "on", "yes"}
    accepted_version = str(form.get("terms_version", "")).strip()
    if not agree:
        add_flash(request, "You must agree to the terms before continuing.", "error")
        return RedirectResponse(url=f"/access/terms?next={quote(next_path, safe='/%?=&')}", status_code=303)
    try:
        record_terms_acceptance(
            request=request,
            repo=repo,
            user_principal=user.user_principal,
            accepted_version=accepted_version,
        )
    except Exception as exc:
        add_flash(request, f"Could not record acceptance: {exc}", "error")
        return RedirectResponse(url=f"/access/terms?next={quote(next_path, safe='/%?=&')}", status_code=303)

    add_flash(request, "Terms accepted. Access granted for this version.", "success")
    return RedirectResponse(url=next_path, status_code=303)

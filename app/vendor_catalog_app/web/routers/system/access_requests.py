from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.repository_constants import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.core.security import ACCESS_REQUEST_ALLOWED_ROLES
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/access")


def _allowed_role_options(repo) -> list[str]:
    allowed = set(ACCESS_REQUEST_ALLOWED_ROLES)
    known = [str(role).strip() for role in repo.list_known_roles() if str(role).strip()]
    out = [role for role in known if role in allowed]
    if out:
        return out
    return list(ACCESS_REQUEST_ALLOWED_ROLES)


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
        },
    )
    return request.app.state.templates.TemplateResponse(request, "access_request.html", context)


@router.post("/request")
@require_permission("access_request")
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
        return RedirectResponse(url="/workflows?status=pending&queue=my_submissions", status_code=303)
    except Exception as exc:
        add_flash(request, f"Could not submit access request: {exc}", "error")
        return RedirectResponse(url="/access/request", status_code=303)

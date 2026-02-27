from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/help")


def _safe_return_to(value: str | None, *, fallback: str = "/help") -> str:
    raw = str(value or "").strip()
    if raw.startswith("/help"):
        return raw
    return fallback


@router.post("/feedback")
@require_permission("feedback_submit")
async def help_feedback(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    article_id = str(form.get("article_id") or "").strip() or None
    article_slug = str(form.get("article_slug") or "").strip() or None
    was_helpful_raw = str(form.get("was_helpful") or "").strip().lower()
    was_helpful = was_helpful_raw in {"1", "true", "yes", "y", "up"}
    comment = str(form.get("comment") or "").strip() or None
    page_path = str(form.get("page_path") or request.url.path).strip()
    return_to = _safe_return_to(str(form.get("return_to") or ""))

    repo.record_help_feedback(
        article_id=article_id,
        article_slug=article_slug,
        was_helpful=was_helpful,
        comment=comment,
        user_principal=user.user_principal,
        page_path=page_path,
    )
    add_flash(request, "Thanks for the feedback.", "success")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/report")
@require_permission("report_submit")
async def help_report_issue(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    article_id = str(form.get("article_id") or "").strip() or None
    article_slug = str(form.get("article_slug") or "").strip() or None
    issue_title = str(form.get("issue_title") or "").strip()
    issue_description = str(form.get("issue_description") or "").strip()
    page_path = str(form.get("page_path") or request.url.path).strip()
    return_to = _safe_return_to(str(form.get("return_to") or ""))

    if not issue_title or not issue_description:
        add_flash(request, "Add a title and description before sending the issue.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    repo.record_help_issue(
        article_id=article_id,
        article_slug=article_slug,
        issue_title=issue_title,
        issue_description=issue_description,
        user_principal=user.user_principal,
        page_path=page_path,
    )
    add_flash(request, "Issue sent. Thank you.", "success")
    return RedirectResponse(url=return_to, status_code=303)

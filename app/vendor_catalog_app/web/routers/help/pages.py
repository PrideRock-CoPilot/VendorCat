from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Request, status

from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.utils.markdown import render_safe_markdown

router = APIRouter(prefix="/help")


def _role_tier(user) -> str:
    roles = set(getattr(user, "roles", set()) or set())
    if getattr(user, "is_admin", False) or "vendor_admin" in roles or "vendor_steward" in roles:
        return "admin"
    if "vendor_editor" in roles:
        return "editor"
    return "viewer"


def _parse_visibility(value: str | None) -> set[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return {"viewer", "editor", "admin"}
    tokens = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return tokens or {"viewer", "editor", "admin"}


def _is_visible(visibility: str | None, role: str) -> bool:
    allowed = _parse_visibility(visibility)
    if "admin" in allowed and role == "admin":
        return True
    if role == "admin":
        return True
    if role == "editor" and "editor" in allowed:
        return True
    if role == "viewer" and "viewer" in allowed:
        return True
    if role == "editor" and "viewer" in allowed:
        return True
    return False


def _normalize_search_text(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_markdown(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[#>*_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _score_article(query: str, article: dict[str, Any]) -> int:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return 0
    title = _normalize_search_text(str(article.get("title") or ""))
    content = _normalize_search_text(str(article.get("content_md") or ""))
    score = 0
    if normalized_query in title:
        score += 12
    if normalized_query in content:
        score += 4
    for token in normalized_query.split(" "):
        if token in title:
            score += 5
        if token in content:
            score += 1
    return score


def _build_snippet(query: str, article: dict[str, Any]) -> str:
    text = _strip_markdown(article.get("content_md") or "")
    if not text:
        return ""
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return text[:160].strip()
    idx = _normalize_search_text(text).find(normalized_query)
    if idx < 0:
        return text[:160].strip()
    start = max(0, idx - 40)
    end = min(len(text), idx + 120)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _group_nav_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        section = str(item.get("section") or "General").strip() or "General"
        grouped.setdefault(section, []).append(item)
    output: list[dict[str, Any]] = []
    for section in sorted(grouped.keys()):
        rows = sorted(grouped[section], key=lambda row: (str(row.get("title") or ""), str(row.get("slug") or "")))
        output.append({"section": section, "items": rows})
    return output


def _help_context(request: Request, user, *, active_slug: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return base_template_context(
        request=request,
        context=user,
        title="Help Center",
        active_nav="help",
        extra={"help_active_slug": active_slug, **(extra or {})},
    )


@router.get("")
def help_index(request: Request, q: str = ""):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Help Center")

    role = _role_tier(user)
    index_rows = [row for row in repo.list_help_article_index() if _is_visible(row.get("role_visibility"), role)]
    nav_sections = _group_nav_items(index_rows)

    search_query = (q or "").strip()
    search_results: list[dict[str, Any]] = []
    if search_query:
        full_rows = [row for row in repo.list_help_articles_full() if _is_visible(row.get("role_visibility"), role)]
        scored = []
        for row in full_rows:
            score = _score_article(search_query, row)
            if score <= 0:
                continue
            record = dict(row)
            record["score"] = score
            record["snippet"] = _build_snippet(search_query, row)
            scored.append(record)
        search_results = sorted(scored, key=lambda row: (-int(row.get("score", 0)), str(row.get("title") or "")))

    context = _help_context(
        request,
        user,
        active_slug=None,
        extra={
            "nav_sections": nav_sections,
            "search_query": search_query,
            "search_results": search_results,
            "show_index": not search_query,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "help_center.html", context)


@router.get("/{slug}")
def help_article(request: Request, slug: str):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Help Article")

    role = _role_tier(user)
    index_rows = [row for row in repo.list_help_article_index() if _is_visible(row.get("role_visibility"), role)]
    nav_sections = _group_nav_items(index_rows)

    article = repo.get_help_article_by_slug(slug)
    if article is None:
        context = _help_context(
            request,
            user,
            active_slug=None,
            extra={
                "nav_sections": nav_sections,
                "article_missing": True,
                "article_slug": slug,
            },
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "help_center.html",
            context,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if not _is_visible(article.get("role_visibility"), role):
        context = _help_context(
            request,
            user,
            active_slug=None,
            extra={
                "nav_sections": nav_sections,
                "article_forbidden": True,
                "article_slug": slug,
            },
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "help_center.html",
            context,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    content_html = render_safe_markdown(str(article.get("content_md") or ""))
    context = _help_context(
        request,
        user,
        active_slug=str(article.get("slug") or ""),
        extra={
            "nav_sections": nav_sections,
            "article": article,
            "article_html": content_html,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "help_center.html", context)

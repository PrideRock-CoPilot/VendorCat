from __future__ import annotations

import re
import uuid
from typing import Any, Literal, cast

import bleach
import markdown as markdown_lib
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.responses import api_error, api_json, parse_json_body
from apps.core.services.permission_registry import authorize_mutation
from apps.core.services.policy_engine import PolicyEngine
from apps.help_center.constants import HELP_ARTICLE_CATEGORIES, HELP_FEEDBACK_RATINGS
from apps.help_center.contracts import HelpFeedbackRequest, HelpIssueRequest, HelpSearchResult
from apps.help_center.models import HelpArticle, HelpFeedback, HelpIssue
from apps.identity.services import build_policy_snapshot, sync_user_directory

_ALLOWED_TAGS = ["p", "ul", "ol", "li", "a", "code", "pre", "h1", "h2", "h3", "h4", "strong", "em", "blockquote"]
_ALLOWED_ATTRS = {"a": ["href", "title", "rel", "target"]}
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(value: str) -> str:
    base = value.lower().strip().replace(" ", "-")
    base = _SLUG_RE.sub("-", base)
    return re.sub(r"-+", "-", base).strip("-")


def _render_sanitized_markdown(markdown_body: str) -> str:
    rendered = markdown_lib.markdown(markdown_body, extensions=["extra"])
    return bleach.clean(rendered, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _serialize_article(record: HelpArticle) -> dict[str, Any]:
    return {
        "article_id": record.article_id,
        "slug": record.slug,
        "title": record.title,
        "markdown_body": record.markdown_body,
        "rendered_html": record.rendered_html,
        "published": bool(record.published),
        "view_count": int(record.view_count),
        "author": record.author,
        "category": record.category,
    }


def _legacy_article_payload(record: HelpArticle) -> dict[str, str]:
    return {
        "article_id": record.article_id,
        "article_title": record.article_title,
        "category": record.category,
        "content_markdown": record.content_markdown[:200],
        "is_published": str(record.is_published),
        "view_count": str(record.view_count),
        "author": record.author,
    }


def _normalize_category(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in HELP_ARTICLE_CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(HELP_ARTICLE_CATEGORIES)}")
    return normalized


def _permission_denied(request: HttpRequest, permission: str) -> JsonResponse:
    return api_error(request, code="forbidden", message=f"Missing permission: {permission}", status=403)


def _identity_snapshot(request: HttpRequest):
    from apps.core.contracts.identity import resolve_identity_context

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    return identity, snapshot


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    query = str(request.GET.get("q", "")).strip().lower()
    records = list(
        HelpArticle.objects.filter(published=True).order_by("slug")  # type: ignore[attr-defined]
    )
    if query:
        records = [record for record in records if query in record.title.lower() or query in record.markdown_body.lower()]

    return render(
        request,
        "help_center/index.html",
        {
            "page_title": "Help Center",
            "section_name": "Help Center",
            "items": [_serialize_article(record) for record in records],
            "query": query,
        },
    )


@require_http_methods(["GET"])
def article_page(request: HttpRequest, slug: str) -> HttpResponse:
    record = get_object_or_404(HelpArticle, slug=slug)
    record.view_count += 1
    record.save(update_fields=["view_count", "updated_at"])
    return render(
        request,
        "help_center/article.html",
        {
            "page_title": record.title,
            "item": _serialize_article(record),
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def help_articles_collection_endpoint(request: HttpRequest) -> JsonResponse:
    identity, snapshot = _identity_snapshot(request)

    if request.method == "GET":
        decision = PolicyEngine.decide(snapshot, "help.read")
        if not decision.allowed:
            return _permission_denied(request, "help.read")

        items = [_serialize_article(record) for record in HelpArticle.objects.all().order_by("slug")]  # type: ignore[attr-defined]
        return api_json({"items": items})

    decision = authorize_mutation(snapshot, "POST", "/api/v1/help/articles")
    if not decision.allowed:
        return _permission_denied(request, "help.write")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    title = str(body.get("title", body.get("article_title", ""))).strip()
    markdown_body = str(body.get("markdown_body", body.get("content_markdown", ""))).strip()
    category = str(body.get("category", "faq")).strip() or "faq"
    author = str(body.get("author", identity.display_name)).strip() or identity.display_name
    published = bool(body.get("published", body.get("is_published", False)))
    slug = str(body.get("slug", "")).strip() or _slugify(title)

    if not title:
        return api_error(request, code="invalid_request", message="title is required", status=400)
    if not markdown_body:
        return api_error(request, code="invalid_request", message="markdown_body is required", status=400)
    if not slug:
        return api_error(request, code="invalid_request", message="slug is required", status=400)

    try:
        category = _normalize_category(category)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    if HelpArticle.objects.filter(slug=slug).exists():  # type: ignore[attr-defined]
        return api_error(request, code="conflict", message=f"article slug {slug} already exists", status=409)

    article_id = str(body.get("article_id", "")).strip() or str(uuid.uuid4())
    rendered_html = _render_sanitized_markdown(markdown_body)

    record = HelpArticle.objects.create(  # type: ignore[attr-defined]
        article_id=article_id,
        slug=slug,
        title=title,
        markdown_body=markdown_body,
        rendered_html=rendered_html,
        published=published,
        article_title=title,
        category=category,
        content_markdown=markdown_body,
        is_published=published,
        author=author,
    )

    return api_json(_serialize_article(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def help_article_detail_endpoint(request: HttpRequest, article_id: str) -> JsonResponse:
    identity, snapshot = _identity_snapshot(request)

    try:
        record = HelpArticle.objects.get(article_id=article_id)  # type: ignore[attr-defined]
    except HelpArticle.DoesNotExist:  # type: ignore[attr-defined]
        return api_error(request, code="not_found", message=f"article {article_id} not found", status=404)

    if request.method == "GET":
        decision = PolicyEngine.decide(snapshot, "help.read")
        if not decision.allowed:
            return _permission_denied(request, "help.read")

        record.view_count += 1
        record.save(update_fields=["view_count", "updated_at"])
        return api_json(_legacy_article_payload(record))

    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/help/articles/{article_id}")
    if not decision.allowed:
        return _permission_denied(request, "help.write")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    if "article_title" in body or "title" in body:
        title = str(body.get("title", body.get("article_title", ""))).strip()
        if not title:
            return api_error(request, code="invalid_request", message="title cannot be empty", status=400)
        record.title = title
        record.article_title = title

    if "content_markdown" in body or "markdown_body" in body:
        markdown_body = str(body.get("markdown_body", body.get("content_markdown", ""))).strip()
        record.markdown_body = markdown_body
        record.content_markdown = markdown_body
        record.rendered_html = _render_sanitized_markdown(markdown_body)

    if "category" in body:
        try:
            record.category = _normalize_category(str(body["category"]))
        except ValueError as exc:
            return api_error(request, code="invalid_request", message=str(exc), status=400)

    if "is_published" in body or "published" in body:
        published = bool(body.get("published", body.get("is_published")))
        record.published = published
        record.is_published = published

    if "slug" in body:
        slug = _slugify(str(body["slug"]))
        if not slug:
            return api_error(request, code="invalid_request", message="slug cannot be empty", status=400)
        if HelpArticle.objects.filter(slug=slug).exclude(article_id=record.article_id).exists():  # type: ignore[attr-defined]
            return api_error(request, code="conflict", message=f"article slug {slug} already exists", status=409)
        record.slug = slug

    record.save()
    return api_json(_legacy_article_payload(record))


@require_http_methods(["GET"])
def help_article_by_slug_endpoint(request: HttpRequest, slug: str) -> JsonResponse:
    _, snapshot = _identity_snapshot(request)
    decision = PolicyEngine.decide(snapshot, "help.read")
    if not decision.allowed:
        return _permission_denied(request, "help.read")

    record = get_object_or_404(HelpArticle, slug=slug)
    record.view_count += 1
    record.save(update_fields=["view_count", "updated_at"])
    return api_json(_serialize_article(record))


@require_http_methods(["GET"])
def help_search_endpoint(request: HttpRequest) -> JsonResponse:
    _, snapshot = _identity_snapshot(request)
    decision = PolicyEngine.decide(snapshot, "help.read")
    if not decision.allowed:
        return _permission_denied(request, "help.read")

    query = str(request.GET.get("q", "")).strip().lower()
    if not query:
        return api_json({"items": []})

    candidates = list(HelpArticle.objects.filter(published=True).order_by("slug"))  # type: ignore[attr-defined]
    results: list[HelpSearchResult] = []
    for record in candidates:
        title_lower = record.title.lower()
        body_lower = record.markdown_body.lower()
        if query not in title_lower and query not in body_lower:
            continue

        score = 0.0
        score += 100.0 if query in title_lower else 0.0
        score += float(body_lower.count(query) * 10)

        snippet_source = record.markdown_body.strip().replace("\n", " ")
        snippet = snippet_source[:180]
        results.append(HelpSearchResult(slug=record.slug, title=record.title, snippet=snippet, score=score))

    ordered = sorted(results, key=lambda item: (-item.score, item.slug))
    return api_json({"items": [item.__dict__ for item in ordered]})


@csrf_exempt
@require_http_methods(["POST"])
def help_feedback_endpoint(request: HttpRequest) -> JsonResponse:
    identity, snapshot = _identity_snapshot(request)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/help/feedback")
    if not decision.allowed:
        return _permission_denied(request, "help.feedback.write")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    dto = HelpFeedbackRequest(
        slug=str(body.get("slug", "")).strip(),
        rating=cast(Literal["up", "down"], str(body.get("rating", "")).strip().lower()),
        comment=str(body.get("comment", "")).strip(),
        submitted_by=str(body.get("submitted_by", identity.user_principal)).strip() or identity.user_principal,
    )

    try:
        dto.validate()
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    if dto.rating not in HELP_FEEDBACK_RATINGS:
        return api_error(request, code="invalid_request", message="rating must be up or down", status=400)
    if not HelpArticle.objects.filter(slug=dto.slug).exists():  # type: ignore[attr-defined]
        return api_error(request, code="not_found", message=f"article slug {dto.slug} not found", status=404)

    record = HelpFeedback.objects.create(  # type: ignore[attr-defined]
        slug=dto.slug,
        rating=dto.rating,
        comment=dto.comment,
        submitted_by=dto.submitted_by,
    )

    return api_json(
        {
            "feedback_id": int(record.id),
            "slug": dto.slug,
            "rating": dto.rating,
            "submitted_by": dto.submitted_by,
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST"])
def help_issue_endpoint(request: HttpRequest) -> JsonResponse:
    identity, snapshot = _identity_snapshot(request)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/help/issues")
    if not decision.allowed:
        return _permission_denied(request, "help.issue.write")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    screenshot_raw = body.get("screenshot_path")
    screenshot_path = str(screenshot_raw).strip() if isinstance(screenshot_raw, str) else None

    dto = HelpIssueRequest(
        slug=str(body.get("slug", "")).strip(),
        issue_text=str(body.get("issue_text", "")).strip(),
        screenshot_path=screenshot_path,
        submitted_by=str(body.get("submitted_by", identity.user_principal)).strip() or identity.user_principal,
    )

    try:
        dto.validate()
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    if not HelpArticle.objects.filter(slug=dto.slug).exists():  # type: ignore[attr-defined]
        return api_error(request, code="not_found", message=f"article slug {dto.slug} not found", status=404)

    record = HelpIssue.objects.create(  # type: ignore[attr-defined]
        slug=dto.slug,
        issue_text=dto.issue_text,
        screenshot_path=dto.screenshot_path or "",
        submitted_by=dto.submitted_by,
    )

    return api_json(
        {
            "issue_id": int(record.id),
            "slug": dto.slug,
            "submitted_by": dto.submitted_by,
            "screenshot_path": dto.screenshot_path,
        },
        status=201,
    )

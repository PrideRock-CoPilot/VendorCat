from __future__ import annotations

import re
from collections.abc import Iterable

REQUIRED_WORKFLOW_SECTIONS = (
    "what you need",
    "steps",
    "expected result",
    "common problems and fixes",
    "example",
)

LEGACY_WORKFLOW_SECTIONS = (
    "scenario",
    "navigate",
    "steps",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text)
    parts = re.split(r"[.!?]+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _word_count(text: str) -> int:
    return len([token for token in re.split(r"\s+", text) if token])


def validate_help_articles(articles: Iterable[dict]) -> list[str]:
    errors: list[str] = []
    seen_slugs: set[str] = set()
    for article in articles:
        slug = str(article.get("slug") or "").strip()
        title = str(article.get("title") or "").strip()
        content = str(article.get("content_md") or "").strip()
        if "\\n" in content or "\\r" in content:
            content = content.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
        article_type = str(article.get("article_type") or "").strip().lower()

        if not title:
            errors.append(f"{slug or 'unknown'} missing title")
        if not slug:
            errors.append("article missing slug")
        if slug:
            if slug in seen_slugs:
                errors.append(f"duplicate slug: {slug}")
            seen_slugs.add(slug)

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        for para in paragraphs:
            if _word_count(para) > 90:
                errors.append(f"{slug} paragraph too long")

        sentence_list = _sentences(content)
        if sentence_list:
            avg_words = sum(_word_count(s) for s in sentence_list) / float(len(sentence_list))
            if avg_words > 18:
                errors.append(f"{slug} sentences too long")

        if article_type == "workflow":
            headings = [
                _normalize(match.group(1))
                for match in re.finditer(r"^##\s+(.+)$", content, flags=re.M)
            ]
            has_modern_structure = all(required in headings for required in REQUIRED_WORKFLOW_SECTIONS)
            has_legacy_structure = all(required in headings for required in LEGACY_WORKFLOW_SECTIONS)
            if not has_modern_structure and not has_legacy_structure:
                for required in REQUIRED_WORKFLOW_SECTIONS:
                    if required not in headings:
                        errors.append(f"{slug} missing section: {required}")

    return errors

from __future__ import annotations

from collections.abc import Iterable

import bleach
from markdown import markdown

_ALLOWED_TAGS: list[str] = [
    "a",
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "code",
    "pre",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "img",
]

_ALLOWED_ATTRS: dict[str, Iterable[str]] = {
    "a": ["href", "title", "target", "rel"],
    "code": ["class"],
    "img": ["src", "alt", "title", "width", "height"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_safe_markdown(text: str) -> str:
    normalized = str(text or "")
    if "\\n" in normalized or "\\r" in normalized:
        normalized = normalized.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
    raw_html = markdown(
        normalized,
        extensions=["extra", "sane_lists"],
        output_format="html",
    )
    cleaned = bleach.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    return bleach.linkify(cleaned, skip_tags=["pre", "code"])

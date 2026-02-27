from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class HelpArticle:
    article_id: str
    slug: str
    title: str
    markdown_body: str
    rendered_html: str
    published: bool


@dataclass(frozen=True)
class HelpSearchResult:
    slug: str
    title: str
    snippet: str
    score: float


@dataclass(frozen=True)
class HelpFeedbackRequest:
    slug: str
    rating: Literal["up", "down"]
    comment: str
    submitted_by: str

    def validate(self) -> None:
        if not self.slug.strip():
            raise ValueError("slug is required")
        if self.rating not in {"up", "down"}:
            raise ValueError("rating must be up or down")
        if not self.submitted_by.strip():
            raise ValueError("submitted_by is required")


@dataclass(frozen=True)
class HelpIssueRequest:
    slug: str
    issue_text: str
    screenshot_path: str | None
    submitted_by: str

    def validate(self) -> None:
        if not self.slug.strip():
            raise ValueError("slug is required")
        if not self.issue_text.strip():
            raise ValueError("issue_text is required")
        if not self.submitted_by.strip():
            raise ValueError("submitted_by is required")

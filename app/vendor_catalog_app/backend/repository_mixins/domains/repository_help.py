from __future__ import annotations

from typing import Any


class RepositoryHelpMixin:
    def list_help_article_index(self) -> list[dict[str, Any]]:
        def _load() -> list[dict[str, Any]]:
            rows = self._query_file(
                "help/select_help_articles_index.sql",
                columns=[
                    "article_id",
                    "slug",
                    "title",
                    "section",
                    "article_type",
                    "role_visibility",
                    "owned_by",
                    "updated_at",
                    "updated_by",
                ],
                vendor_help_article=self._table("vendor_help_article"),
            )
            return rows.to_dict("records") if not rows.empty else []

        return self._cached(("help_article_index",), _load, ttl_seconds=180)

    def list_help_articles_full(self) -> list[dict[str, Any]]:
        def _load() -> list[dict[str, Any]]:
            rows = self._query_file(
                "help/select_help_articles_full.sql",
                columns=[
                    "article_id",
                    "slug",
                    "title",
                    "section",
                    "article_type",
                    "role_visibility",
                    "content_md",
                    "owned_by",
                    "updated_at",
                    "updated_by",
                ],
                vendor_help_article=self._table("vendor_help_article"),
            )
            return rows.to_dict("records") if not rows.empty else []

        return self._cached(("help_articles_full",), _load, ttl_seconds=180)

    def get_help_article_by_slug(self, slug: str) -> dict[str, Any] | None:
        normalized = str(slug or "").strip()
        if not normalized:
            return None

        def _load() -> dict[str, Any] | None:
            rows = self._query_file(
                "help/select_help_article_by_slug.sql",
                params=(normalized,),
                columns=[
                    "article_id",
                    "slug",
                    "title",
                    "section",
                    "article_type",
                    "role_visibility",
                    "content_md",
                    "owned_by",
                    "updated_at",
                    "updated_by",
                    "created_at",
                    "created_by",
                ],
                vendor_help_article=self._table("vendor_help_article"),
            )
            if rows.empty:
                return None
            return rows.iloc[0].to_dict()

        return self._cached(("help_article", normalized.lower()), _load, ttl_seconds=180)

    def create_help_article(
        self,
        *,
        slug: str,
        title: str,
        section: str,
        article_type: str,
        role_visibility: str,
        content_md: str,
        owned_by: str,
        actor_user_principal: str,
    ) -> str:
        article_id = self._new_id("help")
        now = self._now()
        self._execute_file(
            "inserts/create_help_article.sql",
            params=(
                article_id,
                slug,
                title,
                section,
                article_type,
                role_visibility,
                content_md,
                owned_by,
                now,
                actor_user_principal,
                now,
                actor_user_principal,
            ),
            vendor_help_article=self._table("vendor_help_article"),
        )
        return article_id

    def record_help_feedback(
        self,
        *,
        article_id: str | None,
        article_slug: str | None,
        was_helpful: bool,
        comment: str | None,
        user_principal: str | None,
        page_path: str | None,
    ) -> str:
        feedback_id = self._new_id("helpfb")
        now = self._now()
        self._execute_file(
            "inserts/create_help_feedback.sql",
            params=(
                feedback_id,
                article_id,
                article_slug,
                bool(was_helpful),
                (comment or "").strip() or None,
                (user_principal or "").strip() or None,
                (page_path or "").strip() or None,
                now,
            ),
            vendor_help_feedback=self._table("vendor_help_feedback"),
        )
        return feedback_id

    def record_help_issue(
        self,
        *,
        article_id: str | None,
        article_slug: str | None,
        issue_title: str,
        issue_description: str,
        user_principal: str | None,
        page_path: str | None,
    ) -> str:
        issue_id = self._new_id("helpissue")
        now = self._now()
        self._execute_file(
            "inserts/create_help_issue.sql",
            params=(
                issue_id,
                article_id,
                article_slug,
                issue_title,
                issue_description,
                (page_path or "").strip() or None,
                (user_principal or "").strip() or None,
                now,
            ),
            vendor_help_issue=self._table("vendor_help_issue"),
        )
        return issue_id

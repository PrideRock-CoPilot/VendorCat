from __future__ import annotations

import logging
import re
import uuid
from typing import Any

import pandas as pd

LOGGER = logging.getLogger(__name__)

class RepositoryDocumentsMixin:
    def get_doc_link(self, doc_id: str) -> dict[str, Any] | None:
        rows = self._query_file(
            "ingestion/select_doc_link_by_id.sql",
            params=(doc_id,),
            columns=[
                "doc_id",
                "entity_type",
                "entity_id",
                "doc_title",
                "doc_url",
                "doc_type",
                "tags",
                "owner",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_document_link=self._table("app_document_link"),
        )
        if rows.empty:
            return None
        row = rows.iloc[0].to_dict()
        row["doc_fqdn"] = re.sub(r"^https?://", "", str(row.get("doc_url") or "")).split("/", 1)[0].lower()
        return row

    def list_docs(self, entity_type: str, entity_id: str) -> pd.DataFrame:
        allowed = {"vendor", "project", "offering", "demo"}
        if entity_type not in allowed:
            return pd.DataFrame(
                columns=[
                    "doc_id",
                    "entity_type",
                    "entity_id",
                    "doc_title",
                    "doc_url",
                    "doc_type",
                    "tags",
                    "owner",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                ]
            )
        out = self._query_file(
            "ingestion/select_docs_by_entity.sql",
            params=(entity_type, entity_id),
            columns=[
                "doc_id",
                "entity_type",
                "entity_id",
                "doc_title",
                "doc_url",
                "doc_type",
                "tags",
                "owner",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_document_link=self._table("app_document_link"),
        )
        if not out.empty and "doc_url" in out.columns:
            out["doc_fqdn"] = out["doc_url"].fillna("").astype(str).str.extract(r"https?://([^/]+)", expand=False).fillna("").str.lower()
        return out

    def create_doc_link(
        self,
        *,
        entity_type: str,
        entity_id: str,
        doc_title: str,
        doc_url: str,
        doc_type: str,
        tags: str | None,
        owner: str | None,
        actor_user_principal: str,
        doc_fqdn: str | None = None,
    ) -> str:
        allowed = {"vendor", "project", "offering", "demo"}
        if entity_type not in allowed:
            raise ValueError("Unsupported document entity type.")
        clean_title = (doc_title or "").strip()
        clean_url = (doc_url or "").strip()
        clean_type = (doc_type or "").strip()
        if not clean_title:
            raise ValueError("Document title is required.")
        if not clean_url:
            raise ValueError("Document URL is required.")
        if not clean_type:
            raise ValueError("Document type is required.")
        clean_fqdn = (doc_fqdn or "").strip().lower()
        clean_owner = (owner or "").strip()
        if not clean_owner:
            clean_owner = str(actor_user_principal or "").strip()
        resolved_owner = self.resolve_user_login_identifier(clean_owner)
        if not resolved_owner:
            raise ValueError("Owner must exist in the app user directory.")

        doc_id = self._new_id("doc")
        now = self._now()
        row = {
            "doc_id": doc_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "doc_title": clean_title,
            "doc_url": clean_url,
            "doc_type": clean_type,
            "doc_fqdn": clean_fqdn or None,
            "tags": (tags or "").strip() or None,
            "owner": resolved_owner,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_user_principal,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        self._execute_file(
            "inserts/create_doc_link.sql",
            params=(
                doc_id,
                entity_type,
                entity_id,
                clean_title,
                clean_url,
                clean_type,
                row["tags"],
                resolved_owner,
                True,
                now,
                actor_user_principal,
                now,
                actor_user_principal,
            ),
            app_document_link=self._table("app_document_link"),
        )
        self._write_audit_entity_change(
            entity_name="app_document_link",
            entity_id=doc_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return doc_id

    def update_doc_link(self, *, doc_id: str, actor_user_principal: str, updates: dict[str, Any], reason: str) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        current = self.get_doc_link(doc_id)
        if current is None:
            raise ValueError("Document link not found.")
        allowed = {"doc_title", "doc_url", "doc_type", "tags", "owner"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No updates were provided.")
        if "owner" in clean_updates:
            resolved_owner = self.resolve_user_login_identifier(str(clean_updates.get("owner") or "").strip())
            if not resolved_owner:
                raise ValueError("Owner must exist in the app user directory.")
            clean_updates["owner"] = resolved_owner
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        now = self._now()
        set_clause = ", ".join([f"{k} = %s" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_user_principal, doc_id]
        self._execute_file(
            "updates/update_doc_link.sql",
            params=tuple(params),
            app_document_link=self._table("app_document_link"),
            set_clause=set_clause,
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="app_document_link",
            entity_id=doc_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def remove_doc_link(self, *, doc_id: str, actor_user_principal: str) -> None:
        current = self.get_doc_link(doc_id)
        if current is None:
            raise ValueError("Document link not found.")
        self._execute_file(
            "updates/remove_doc_link_soft.sql",
            params=(self._now(), actor_user_principal, doc_id),
            app_document_link=self._table("app_document_link"),
        )
        self._write_audit_entity_change(
            entity_name="app_document_link",
            entity_id=doc_id,
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=current,
            after_json=None,
            request_id=None,
        )


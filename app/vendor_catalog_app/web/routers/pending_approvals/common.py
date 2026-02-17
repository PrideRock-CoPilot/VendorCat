from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote, urlencode

from vendor_catalog_app.core.security import (
    MAX_APPROVAL_LEVEL,
    MIN_CHANGE_APPROVAL_LEVEL,
    approval_level_label,
    required_approval_level,
)
from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID

LOGGER = logging.getLogger(__name__)

WORKFLOW_QUEUES = ["all", "pending_review", "my_submissions", "my_approvals"]
ENTERPRISE_SCOPE_VALUES = {"*", "all", "enterprise"}
ENTERPRISE_SCOPE_LEVELS = {"all", "enterprise", "global", "full_enterprise"}
TERMINAL_WORKFLOW_STATUSES = {"approved", "rejected"}


def _safe_return_to(value: str | None) -> str:
    if not value:
        return "/workflows"
    if (
        value.startswith("/workflows")
        or value.startswith("/vendors")
        or value.startswith("/vendor-360")
        or value.startswith("/projects")
    ):
        return value
    return "/workflows"


def _normalize_status(value: str | None, allowed_statuses: set[str]) -> str:
    cleaned = str(value or "pending").strip().lower()
    if cleaned not in allowed_statuses:
        return "pending"
    return cleaned


def _workflow_status_options(repo) -> list[str]:
    options = [str(item).strip().lower() for item in repo.list_workflow_status_options() if str(item).strip()]
    seen: set[str] = set()
    out: list[str] = []
    for value in options:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _workflow_filter_status_options(repo) -> list[str]:
    options = ["pending"]
    options.extend(_workflow_status_options(repo))
    options.append("all")
    seen: set[str] = set()
    out: list[str] = []
    for value in options:
        normalized = str(value).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _is_terminal_workflow_status(status_value: str | None) -> bool:
    return str(status_value or "").strip().lower() in TERMINAL_WORKFLOW_STATUSES


def _normalize_queue(value: str | None) -> str:
    cleaned = str(value or "pending_review").strip().lower()
    if cleaned not in WORKFLOW_QUEUES:
        return "pending_review"
    return cleaned


def _payload_obj(raw_payload: str) -> dict:
    try:
        parsed = json.loads(raw_payload or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _payload_list(payload: dict[str, Any], key: str) -> list[str]:
    raw = payload.get(key)
    if raw is None:
        return []
    if isinstance(raw, list):
        out = [str(item).strip() for item in raw if str(item).strip()]
        return out
    value = str(raw).strip()
    return [value] if value else []


def _payload_offering_ids(payload: dict[str, Any]) -> list[str]:
    found: list[str] = []
    found.extend(_payload_list(payload, "offering_id"))
    found.extend(_payload_list(payload, "linked_offering_id"))
    found.extend(_payload_list(payload, "offering_ids"))
    found.extend(_payload_list(payload, "linked_offering_ids"))
    updates = payload.get("updates")
    if isinstance(updates, dict):
        found.extend(_payload_list(updates, "offering_id"))
        found.extend(_payload_list(updates, "linked_offering_id"))
    return sorted({value for value in found if value})


def _payload_lob_values(payload: dict[str, Any], offering_lob_by_id: dict[str, str]) -> list[str]:
    lobs: list[str] = []
    for key in ("lob", "line_of_business"):
        value = str(payload.get(key, "")).strip()
        if value:
            lobs.append(value)
    updates = payload.get("updates")
    if isinstance(updates, dict):
        value = str(updates.get("lob", "")).strip()
        if value:
            lobs.append(value)
    for offering_id in _payload_offering_ids(payload):
        lob = str(offering_lob_by_id.get(offering_id, "")).strip()
        if lob:
            lobs.append(lob)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in lobs:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return sorted(deduped, key=lambda item: item.lower())


def _payload_summary(payload: dict[str, Any]) -> str:
    candidates: list[str] = []
    for key in ("reason", "change_notes", "notes"):
        value = str(payload.get(key, "")).strip()
        if value:
            candidates.append(value)
    updates = payload.get("updates")
    if isinstance(updates, dict):
        updates_summary = ", ".join(sorted([str(key) for key in updates.keys() if str(key).strip()]))
        if updates_summary:
            candidates.append(f"updates: {updates_summary}")
    if not candidates:
        return "-"
    merged = " | ".join(candidates)
    merged = re.sub(r"\s+", " ", merged).strip()
    if len(merged) <= 120:
        return merged
    return f"{merged[:117]}..."


def _status_allows_queue(status_value: str, queue_value: str, can_decide: bool, requester_match: bool) -> bool:
    status = str(status_value or "").strip().lower()
    if queue_value == "all":
        return True
    if queue_value == "pending_review":
        return not _is_terminal_workflow_status(status)
    if queue_value == "my_submissions":
        return requester_match
    if queue_value == "my_approvals":
        return (not _is_terminal_workflow_status(status)) and can_decide
    return True


def _required_level(row: dict) -> int:
    payload = _payload_obj(str(row.get("requested_payload_json") or ""))
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    try:
        level = int(meta.get("approval_level_required", required_approval_level(str(row.get("change_type") or ""))))
    except Exception:
        level = required_approval_level(str(row.get("change_type") or ""))
    return max(MIN_CHANGE_APPROVAL_LEVEL, min(level, MAX_APPROVAL_LEVEL))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return int(value) != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _user_refs(repo, user) -> set[str]:
    refs = {str(user.user_principal or "").strip().lower()}
    try:
        resolved = str(repo.resolve_user_login_identifier(user.user_principal) or "").strip().lower()
        if resolved:
            refs.add(resolved)
    except Exception:
        LOGGER.debug("Failed to resolve login identifier for '%s'.", user.user_principal, exc_info=True)
    try:
        actor_ref = str(repo._actor_ref(user.user_principal) or "").strip().lower()
        if actor_ref:
            refs.add(actor_ref)
    except Exception:
        LOGGER.debug("Failed to resolve actor reference for '%s'.", user.user_principal, exc_info=True)
    return {ref for ref in refs if ref}


def _user_scope(repo, user) -> tuple[set[str], bool]:
    if "vendor_admin" in set(user.roles):
        return set(), True
    refs = _user_refs(repo, user)
    grants = repo.list_scope_grants().to_dict("records")
    scoped_orgs: set[str] = set()
    for row in grants:
        if not _as_bool(row.get("active_flag", True)):
            continue
        principal = str(row.get("user_principal") or "").strip().lower()
        if principal not in refs:
            continue
        org_id = str(row.get("org_id") or "").strip()
        scope_level = str(row.get("scope_level") or "").strip().lower()
        if org_id.lower() in ENTERPRISE_SCOPE_VALUES or scope_level in ENTERPRISE_SCOPE_LEVELS:
            return set(), True
        if org_id:
            scoped_orgs.add(org_id.upper())
    return scoped_orgs, False


def _payload_org_values(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("org_id", "owner_org_id"):
        raw = payload.get(key)
        if raw is None:
            continue
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
        else:
            value = str(raw).strip()
            if value:
                values.append(value)
    updates = payload.get("updates")
    if isinstance(updates, dict):
        for key in ("org_id", "owner_org_id"):
            value = str(updates.get(key) or "").strip()
            if value:
                values.append(value)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _row_in_user_scope(
    *,
    row: dict[str, Any],
    user_scoped_orgs: set[str],
    user_has_enterprise_scope: bool,
) -> bool:
    if user_has_enterprise_scope:
        return True
    if not user_scoped_orgs:
        return False
    row_orgs = {str(item).strip().upper() for item in row.get("_org_values", []) if str(item).strip()}
    if not row_orgs:
        return False
    return bool(row_orgs.intersection(user_scoped_orgs))


def _normalize_for_compare(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value).strip() or None


def _display_value(value: Any) -> str:
    normalized = _normalize_for_compare(value)
    if normalized is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value)


def _first_row(df) -> dict[str, Any]:
    if df is None or getattr(df, "empty", True):
        return {}
    try:
        return df.iloc[0].to_dict()
    except Exception:
        return {}


def _resolve_current_value(
    *,
    field_key: str,
    snapshots: dict[str, dict[str, Any]],
) -> tuple[Any, str]:
    for source_name in ("data_flow", "doc_link", "offering_profile", "offering", "project", "vendor"):
        source = snapshots.get(source_name, {})
        if field_key in source:
            return source.get(field_key), source_name
    return None, "-"


def _build_side_by_side_rows(repo, row: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, str]]:
    vendor_id = str(row.get("vendor_id") or "").strip()
    if vendor_id == GLOBAL_CHANGE_VENDOR_ID:
        vendor_id = str(payload.get("vendor_id") or "").strip()

    offering_ids = _payload_offering_ids(payload)
    offering_id = offering_ids[0] if offering_ids else str(payload.get("offering_id") or "").strip()
    project_id = str(payload.get("project_id") or "").strip()
    doc_id = str(payload.get("doc_id") or "").strip()
    data_flow_id = str(payload.get("data_flow_id") or "").strip()

    snapshots: dict[str, dict[str, Any]] = {
        "vendor": {},
        "offering": {},
        "offering_profile": {},
        "project": {},
        "doc_link": {},
        "data_flow": {},
    }

    try:
        if vendor_id:
            snapshots["vendor"] = _first_row(repo.get_vendor_profile(vendor_id))
    except Exception:
        LOGGER.debug("Failed to load vendor snapshot for '%s'.", vendor_id, exc_info=True)

    try:
        if offering_id:
            snapshots["offering"] = _first_row(repo.get_offerings_by_ids([offering_id]))
    except Exception:
        LOGGER.debug("Failed to load offering snapshot for '%s'.", offering_id, exc_info=True)

    if not vendor_id and snapshots["offering"]:
        vendor_id = str(snapshots["offering"].get("vendor_id") or "").strip()

    try:
        if vendor_id and offering_id:
            snapshots["offering_profile"] = dict(repo.get_offering_profile(vendor_id, offering_id) or {})
    except Exception:
        LOGGER.debug(
            "Failed to load offering profile snapshot for vendor '%s' offering '%s'.",
            vendor_id,
            offering_id,
            exc_info=True,
        )

    try:
        if project_id:
            snapshots["project"] = dict(repo.get_project_by_id(project_id) or {})
    except Exception:
        LOGGER.debug("Failed to load project snapshot for '%s'.", project_id, exc_info=True)

    if not vendor_id and snapshots["project"]:
        vendor_id = str(snapshots["project"].get("vendor_id") or "").strip()

    try:
        if doc_id:
            snapshots["doc_link"] = dict(repo.get_doc_link(doc_id) or {})
    except Exception:
        LOGGER.debug("Failed to load document snapshot for '%s'.", doc_id, exc_info=True)

    try:
        if vendor_id and offering_id and data_flow_id:
            snapshots["data_flow"] = dict(
                repo.get_offering_data_flow(vendor_id=vendor_id, offering_id=offering_id, data_flow_id=data_flow_id) or {}
            )
    except Exception:
        LOGGER.debug(
            "Failed to load data-flow snapshot for vendor '%s' offering '%s' flow '%s'.",
            vendor_id,
            offering_id,
            data_flow_id,
            exc_info=True,
        )

    proposed_rows: list[tuple[str, Any]] = []
    updates = payload.get("updates")
    if isinstance(updates, dict):
        for key in sorted(updates.keys()):
            proposed_rows.append((f"updates.{key}", updates.get(key)))
    for key in sorted(payload.keys()):
        if key in {"_meta", "updates"}:
            continue
        proposed_rows.append((key, payload.get(key)))

    out: list[dict[str, str]] = []
    for full_field, proposed_value in proposed_rows:
        field_key = full_field.split(".", 1)[1] if full_field.startswith("updates.") else full_field
        current_value, source_name = _resolve_current_value(field_key=field_key, snapshots=snapshots)
        current_norm = _normalize_for_compare(current_value)
        proposed_norm = _normalize_for_compare(proposed_value)
        if current_norm is None and proposed_norm is None:
            status = "same"
        elif current_norm is None and proposed_norm is not None:
            status = "new"
        elif current_norm == proposed_norm:
            status = "same"
        else:
            status = "changed"
        out.append(
            {
                "field": full_field,
                "field_key": field_key,
                "current": _display_value(current_value),
                "proposed": _display_value(proposed_value),
                "status": status,
                "source": source_name,
            }
        )
    return out


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _payload_values(payload: dict[str, Any], key: str) -> list[str]:
    values = _payload_list(payload, key)
    updates = payload.get("updates")
    if isinstance(updates, dict):
        values.extend(_payload_list(updates, key))
    return _dedupe_preserve(values)


def _offering_detail_url(*, vendor_id: str, offering_id: str, return_to: str) -> str:
    return f"/vendors/{vendor_id}/offerings/{offering_id}?return_to={quote(return_to, safe='')}"


def _vendor_summary_url(*, vendor_id: str, return_to: str) -> str:
    return f"/vendors/{vendor_id}/summary?return_to={quote(return_to, safe='')}"


def _project_summary_url(*, project_id: str, return_to: str) -> str:
    return f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}"


def _build_target_links(repo, row: dict[str, Any], payload: dict[str, Any], *, return_to: str) -> list[dict[str, str]]:
    target_links: list[dict[str, str]] = []
    row_vendor_id = str(row.get("vendor_id") or "").strip()

    vendor_ids = []
    if row_vendor_id and row_vendor_id != GLOBAL_CHANGE_VENDOR_ID:
        vendor_ids.append(row_vendor_id)
    vendor_ids.extend(_payload_values(payload, "vendor_id"))
    vendor_ids = _dedupe_preserve(vendor_ids)

    offering_ids = _dedupe_preserve(_payload_offering_ids(payload))
    project_ids = _payload_values(payload, "project_id")
    data_flow_ids = _payload_values(payload, "data_flow_id")
    doc_ids = _payload_values(payload, "doc_id")

    vendor_display_by_id: dict[str, str] = {}
    if vendor_ids:
        vendor_rows = repo.get_vendors_by_ids(vendor_ids).to_dict("records")
        for vendor in vendor_rows:
            vendor_id = str(vendor.get("vendor_id") or "").strip()
            if not vendor_id:
                continue
            vendor_display = str(vendor.get("display_name") or vendor.get("legal_name") or vendor_id).strip() or vendor_id
            vendor_display_by_id[vendor_id] = vendor_display

    offering_rows_by_id: dict[str, dict[str, Any]] = {}
    if offering_ids:
        for offering in repo.get_offerings_by_ids(offering_ids).to_dict("records"):
            offering_id = str(offering.get("offering_id") or "").strip()
            if not offering_id:
                continue
            offering_rows_by_id[offering_id] = offering
            inferred_vendor_id = str(offering.get("vendor_id") or "").strip()
            if inferred_vendor_id and inferred_vendor_id not in vendor_ids:
                vendor_ids.append(inferred_vendor_id)
                vendor_display = str(
                    offering.get("vendor_display_name")
                    or offering.get("vendor_legal_name")
                    or inferred_vendor_id
                ).strip() or inferred_vendor_id
                vendor_display_by_id.setdefault(inferred_vendor_id, vendor_display)
    vendor_ids = _dedupe_preserve(vendor_ids)

    for vendor_id in vendor_ids:
        vendor_display = vendor_display_by_id.get(vendor_id, vendor_id)
        target_links.append(
            {
                "label": "Vendor",
                "value": f"{vendor_display} ({vendor_id})",
                "url": _vendor_summary_url(vendor_id=vendor_id, return_to=return_to),
                "link_label": "Open Vendor",
            }
        )

    for offering_id in offering_ids:
        offering = offering_rows_by_id.get(offering_id, {})
        offering_name = str(offering.get("offering_name") or offering_id).strip() or offering_id
        offering_vendor_id = str(offering.get("vendor_id") or "").strip()
        offering_url = (
            _offering_detail_url(vendor_id=offering_vendor_id, offering_id=offering_id, return_to=return_to)
            if offering_vendor_id
            else ""
        )
        target_links.append(
            {
                "label": "Offering",
                "value": f"{offering_name} ({offering_id})",
                "url": offering_url,
                "link_label": "Open Offering" if offering_url else "",
            }
        )

    for project_id in project_ids:
        project = repo.get_project_by_id(project_id) or {}
        project_name = str(project.get("project_name") or project_id).strip() or project_id
        target_links.append(
            {
                "label": "Project",
                "value": f"{project_name} ({project_id})",
                "url": _project_summary_url(project_id=project_id, return_to=return_to),
                "link_label": "Open Project",
            }
        )

    for doc_id in doc_ids:
        doc = repo.get_doc_link(doc_id) or {}
        doc_title = str(doc.get("doc_title") or doc_id).strip() or doc_id
        doc_url = str(doc.get("doc_url") or "").strip()
        target_links.append(
            {
                "label": "Document",
                "value": f"{doc_title} ({doc_id})",
                "url": doc_url,
                "link_label": "Open Document" if doc_url else "",
            }
        )

    entity_type_values = _payload_values(payload, "entity_type")
    entity_id_values = _payload_values(payload, "entity_id")
    if entity_type_values and entity_id_values:
        entity_type = entity_type_values[0].lower()
        entity_id = entity_id_values[0]
        entity_url = ""
        entity_label = "Entity"
        if entity_type == "vendor":
            entity_url = _vendor_summary_url(vendor_id=entity_id, return_to=return_to)
            entity_label = "Vendor Entity"
        elif entity_type == "project":
            entity_url = _project_summary_url(project_id=entity_id, return_to=return_to)
            entity_label = "Project Entity"
        elif entity_type == "offering":
            offering = offering_rows_by_id.get(entity_id)
            if not offering:
                rows = repo.get_offerings_by_ids([entity_id]).to_dict("records")
                offering = rows[0] if rows else {}
            vendor_id = str((offering or {}).get("vendor_id") or "").strip()
            if vendor_id:
                entity_url = _offering_detail_url(vendor_id=vendor_id, offering_id=entity_id, return_to=return_to)
            entity_label = "Offering Entity"
        target_links.append(
            {
                "label": entity_label,
                "value": f"{entity_type}:{entity_id}",
                "url": entity_url,
                "link_label": "Open Entity" if entity_url else "",
            }
        )

    if data_flow_ids:
        flow_offering_id = offering_ids[0] if offering_ids else ""
        flow_vendor_id = ""
        if flow_offering_id:
            flow_vendor_id = str((offering_rows_by_id.get(flow_offering_id) or {}).get("vendor_id") or "").strip()
        if not flow_vendor_id and vendor_ids:
            flow_vendor_id = vendor_ids[0]
        flow_url = ""
        if flow_vendor_id and flow_offering_id:
            flow_url = f"{_offering_detail_url(vendor_id=flow_vendor_id, offering_id=flow_offering_id, return_to=return_to)}&section=dataflow"
        for data_flow_id in data_flow_ids:
            target_links.append(
                {
                    "label": "Data Feed",
                    "value": data_flow_id,
                    "url": flow_url,
                    "link_label": "Open Data Feeds" if flow_url else "",
                }
            )

    return target_links


def _workflow_queue_url(
    *,
    selected_status: str,
    selected_queue: str,
    selected_lob: str,
    selected_requestor: str,
    selected_assignee: str,
    selected_people: str,
) -> str:
    return "/workflows?" + urlencode(
        {
            "status": selected_status,
            "queue": selected_queue,
            "lob": selected_lob,
            "requestor": selected_requestor,
            "assignee": selected_assignee,
            "people": selected_people,
        }
    )


def _load_workflow_queue_view(
    repo,
    user,
    *,
    selected_status: str,
    selected_queue: str,
    selected_lob: str,
    selected_requestor: str,
    selected_assignee: str,
    selected_people: str,
) -> dict[str, Any]:
    selected_people_filter = selected_people.lower()
    query_status = "all" if selected_status in {"pending", "all"} else selected_status
    rows = repo.list_change_requests(status=query_status).to_dict("records")

    offering_ids: set[str] = set()
    vendor_ids: set[str] = set()
    for row in rows:
        payload = _payload_obj(str(row.get("requested_payload_json") or ""))
        row["_payload"] = payload
        if str(row.get("vendor_id") or "").strip() != GLOBAL_CHANGE_VENDOR_ID:
            vendor_ids.add(str(row.get("vendor_id") or "").strip())
        for offering_id in _payload_offering_ids(payload):
            offering_ids.add(offering_id)

    offering_lob_by_id: dict[str, str] = {}
    if offering_ids:
        offering_rows = repo.get_offerings_by_ids(sorted(offering_ids)).to_dict("records")
        for offering in offering_rows:
            offering_id = str(offering.get("offering_id") or "").strip()
            if not offering_id:
                continue
            offering_lob_by_id[offering_id] = str(offering.get("lob") or "").strip()

    vendor_display_by_id: dict[str, str] = {}
    vendor_org_by_id: dict[str, str] = {}
    if vendor_ids:
        vendor_rows = repo.get_vendors_by_ids(sorted(vendor_ids)).to_dict("records")
        for vendor in vendor_rows:
            vendor_id = str(vendor.get("vendor_id") or "").strip()
            if not vendor_id:
                continue
            display_name = str(vendor.get("display_name") or "").strip()
            legal_name = str(vendor.get("legal_name") or "").strip()
            owner_org_id = str(vendor.get("owner_org_id") or "").strip()
            vendor_display_by_id[vendor_id] = display_name or legal_name or vendor_id
            if owner_org_id:
                vendor_org_by_id[vendor_id] = owner_org_id

    user_refs = _user_refs(repo, user)
    scoped_orgs, has_enterprise_scope = _user_scope(repo, user)
    lob_options_set: set[str] = set()
    requestor_options_set: set[str] = set()
    assignee_options_set: set[str] = set()
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        level = _required_level(row)
        row["_approval_level"] = level
        row["_approval_label"] = approval_level_label(level)
        row["_can_decide"] = user.can_review_level(level)
        status_value = str(row.get("status") or "").strip().lower()
        row["_is_terminal"] = _is_terminal_workflow_status(status_value)
        row["_can_quick_decide"] = bool(row["_can_decide"]) and not bool(row["_is_terminal"])

        vendor_id = str(row.get("vendor_id") or "").strip()
        vendor_name = vendor_display_by_id.get(vendor_id, vendor_id)
        row["_vendor_display"] = "global" if vendor_id == GLOBAL_CHANGE_VENDOR_ID else vendor_name
        payload = row.get("_payload") if isinstance(row.get("_payload"), dict) else {}
        meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
        assignee = (
            str(meta.get("assigned_approver") or "")
            or str(meta.get("approver_user_principal") or "")
            or str(meta.get("approver") or "")
        ).strip()
        requestor = str(row.get("requestor_user_principal") or "").strip()
        requestor_raw = str(row.get("requestor_user_principal_raw") or requestor).strip()
        row["_requestor"] = requestor or "-"
        row["_requestor_raw"] = requestor_raw or ""
        row["_assignee"] = assignee or "-"
        row["_lob_values"] = _payload_lob_values(payload, offering_lob_by_id)
        row["_lob_display"] = ", ".join(row["_lob_values"]) if row["_lob_values"] else "-"
        row["_summary"] = _payload_summary(payload)
        org_values = _payload_org_values(payload)
        vendor_org_id = str(vendor_org_by_id.get(vendor_id, "")).strip()
        if vendor_org_id and vendor_org_id.upper() not in {str(item).strip().upper() for item in org_values}:
            org_values.append(vendor_org_id)
        row["_org_values"] = org_values

        if row["_lob_values"]:
            lob_options_set.update(row["_lob_values"])
        if requestor:
            requestor_options_set.add(requestor)
        if assignee:
            assignee_options_set.add(assignee)

        requestor_match = requestor_raw.lower() in user_refs
        if selected_status == "pending" and row["_is_terminal"]:
            continue
        if not _status_allows_queue(status_value, selected_queue, bool(row.get("_can_decide")), requestor_match):
            continue
        if selected_queue == "my_approvals" and user.can_approve_requests:
            if not _row_in_user_scope(
                row=row,
                user_scoped_orgs=scoped_orgs,
                user_has_enterprise_scope=has_enterprise_scope,
            ):
                continue
        if selected_lob and selected_lob != "all":
            if selected_lob.lower() not in {str(item).lower() for item in row["_lob_values"]}:
                continue
        if selected_requestor and selected_requestor != "all":
            if requestor != selected_requestor:
                continue
        if selected_assignee and selected_assignee != "all":
            if assignee != selected_assignee:
                continue
        if selected_people_filter:
            haystack = " ".join(
                [
                    str(row.get("_vendor_display") or ""),
                    requestor,
                    assignee,
                    str(row.get("change_type") or ""),
                    str(row.get("_summary") or ""),
                ]
            ).lower()
            if selected_people_filter not in haystack:
                continue
        filtered_rows.append(row)

    return {
        "rows": filtered_rows,
        "lob_options": sorted(lob_options_set, key=lambda item: item.lower()),
        "requestor_options": sorted(requestor_options_set, key=lambda item: item.lower()),
        "assignee_options": sorted(assignee_options_set, key=lambda item: item.lower()),
    }


# Export underscore-prefixed helpers for module-split star imports.
__all__ = [name for name in globals() if not name.startswith("__")]




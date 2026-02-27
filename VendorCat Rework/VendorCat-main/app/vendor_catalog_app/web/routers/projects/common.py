from __future__ import annotations

from urllib.parse import quote

from fastapi import Request

from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.constants import (
    PROJECT_ASSOCIATION_AUTO_REASON,
    PROJECT_ASSOCIATION_REASON_OPTIONS,
    PROJECT_DEMO_REAUDIT_REASON_OPTIONS,
    PROJECT_OWNER_CHANGE_REASON_OPTIONS,
)
from vendor_catalog_app.web.utils.doc_links import (
    extract_doc_fqdn,
    normalize_doc_tags,
    suggest_doc_title,
    suggest_doc_type,
)

PROJECT_STATUSES = ["all", "draft", "active", "blocked", "complete", "cancelled"]
PROJECT_SECTIONS = [
    ("summary", "Summary"),
    ("ownership", "Ownership"),
    ("offerings", "Offerings"),
    ("demos", "Demos"),
    ("docs", "Documents"),
    ("notes", "Notes"),
]
PROJECT_TYPES_FALLBACK = ["rfp", "poc", "renewal", "implementation", "other"]
PROJECT_STATUS_VALUES = [x for x in PROJECT_STATUSES if x != "all"]


def _safe_return_to(value: str | None) -> str:
    if not value:
        return "/projects"
    if value.startswith("/projects") or value.startswith("/vendors") or value.startswith("/vendor-360"):
        return value
    return "/projects"


def _safe_vendor_id(repo, vendor_id: str | None) -> str | None:
    if not vendor_id:
        return None
    cleaned = str(vendor_id).strip()
    if not cleaned:
        return None
    profile = repo.get_vendor_profile(cleaned)
    if profile.empty:
        return None
    return cleaned


def _request_scope_vendor_id(vendor_id: str | None) -> str:
    cleaned = str(vendor_id or "").strip()
    return cleaned or GLOBAL_CHANGE_VENDOR_ID


def _dedupe_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in seen:
            out.append(cleaned)
            seen.add(cleaned)
    return out


def _resolve_owner_principal_input(repo, form) -> str | None:
    owner_principal = str(form.get("owner_principal", "")).strip()
    owner_display_name = str(form.get("owner_principal_display_name", "")).strip()
    lookup = owner_principal or owner_display_name
    if not lookup:
        return None
    resolved = repo.resolve_user_login_identifier(lookup)
    if not resolved:
        raise ValueError("Project owner must exist in the app user directory.")
    return resolved


def _selected_vendor_rows(repo, vendor_ids: list[str]) -> list[dict[str, str]]:
    cleaned_ids = _dedupe_ordered(vendor_ids)
    if not cleaned_ids:
        return []
    df = repo.get_vendors_by_ids(cleaned_ids)
    by_id: dict[str, dict[str, str]] = {}
    for row in df.to_dict("records"):
        vendor_id = str(row.get("vendor_id") or "").strip()
        if not vendor_id:
            continue
        label = str(row.get("display_name") or row.get("legal_name") or vendor_id)
        by_id[vendor_id] = {"vendor_id": vendor_id, "label": label}
    return [by_id[vendor_id] for vendor_id in cleaned_ids if vendor_id in by_id]


def _selected_offering_rows(repo, offering_ids: list[str]) -> list[dict[str, str]]:
    cleaned_ids = _dedupe_ordered(offering_ids)
    if not cleaned_ids:
        return []
    df = repo.get_offerings_by_ids(cleaned_ids)
    by_id: dict[str, dict[str, str]] = {}
    for row in df.to_dict("records"):
        offering_id = str(row.get("offering_id") or "").strip()
        if not offering_id:
            continue
        offering_name = str(row.get("offering_name") or offering_id)
        vendor_display = str(row.get("vendor_display_name") or row.get("vendor_id") or "Unassigned")
        by_id[offering_id] = {
            "offering_id": offering_id,
            "vendor_id": str(row.get("vendor_id") or "").strip(),
            "label": f"{offering_name} ({offering_id}) - {vendor_display}",
        }
    return [by_id[offering_id] for offering_id in cleaned_ids if offering_id in by_id]


def _project_nav(project_id: str, return_to: str, active_key: str) -> list[dict]:
    encoded_return = quote(return_to, safe="")
    return [
        {
            "key": key,
            "label": label,
            "url": f"/projects/{project_id}/{key}?return_to={encoded_return}",
            "active": key == active_key,
        }
        for key, label in PROJECT_SECTIONS
    ]


def _project_type_options(repo) -> list[str]:
    options = [str(item).strip().lower() for item in repo.list_project_type_options() if str(item).strip()]
    return options or list(PROJECT_TYPES_FALLBACK)


def _normalize_project_type(repo, value: str) -> str:
    allowed = _project_type_options(repo)
    project_type = (value or "other").strip().lower()
    if project_type not in set(allowed):
        raise ValueError(f"Project type must be one of: {', '.join(allowed)}")
    return project_type


def _normalize_project_status(value: str) -> str:
    status = (value or "draft").strip().lower()
    if status not in PROJECT_STATUS_VALUES:
        raise ValueError(f"Status must be one of: {', '.join(PROJECT_STATUS_VALUES)}")
    return status


def _normalize_doc_source(repo, value: str, *, doc_url: str = "") -> str:
    allowed = {str(item).strip().lower() for item in repo.list_doc_source_options() if str(item).strip()}
    if not allowed:
        raise ValueError("Document source lookup options are not configured.")
    source = str(value or "").strip().lower()
    if source:
        if source not in allowed:
            raise ValueError(f"Source must be one of: {', '.join(sorted(allowed))}")
        return source

    inferred = suggest_doc_type(doc_url).strip().lower()
    if inferred in allowed:
        return inferred
    if "other" in allowed:
        return "other"
    return sorted(allowed)[0]


def _prepare_doc_payload(
    repo,
    form_data: dict[str, object],
    *,
    actor_user_principal: str,
) -> dict[str, str]:
    doc_url = str(form_data.get("doc_url", "")).strip()
    doc_type = _normalize_doc_source(repo, str(form_data.get("doc_type", "")), doc_url=doc_url)
    doc_title = str(form_data.get("doc_title", "")).strip()
    raw_tags = form_data.get("tags")
    owner = str(form_data.get("owner", "")).strip() or str(actor_user_principal or "").strip()
    doc_fqdn = extract_doc_fqdn(doc_url)

    if not doc_url:
        raise ValueError("Document link is required.")
    if not doc_type:
        doc_type = suggest_doc_type(doc_url)
    if not doc_title:
        doc_title = suggest_doc_title(doc_url)
    if not doc_title:
        raise ValueError("Document title is required.")
    if len(doc_title) > 120:
        doc_title = doc_title[:120].rstrip()
    owner_login = repo.resolve_user_login_identifier(owner)
    if not owner_login:
        raise ValueError("Owner must exist in the app user directory.")

    collected_tags: list[str] = []
    if isinstance(raw_tags, list):
        collected_tags.extend(str(item or "") for item in raw_tags)
    elif raw_tags is not None:
        collected_tags.append(str(raw_tags or ""))
    normalized_tags = normalize_doc_tags(collected_tags, doc_type="", fqdn="", doc_url="")
    allowed_tags = {str(item).strip().lower() for item in repo.list_doc_tag_options() if str(item).strip()}
    invalid_tags = [tag for tag in normalized_tags if tag not in allowed_tags]
    if invalid_tags:
        raise ValueError(f"Tags must be selected from admin-managed options: {', '.join(sorted(allowed_tags))}")
    return {
        "doc_url": doc_url,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "tags": ",".join(normalized_tags),
        "owner": owner_login,
        "doc_fqdn": doc_fqdn,
    }


def _project_base_context(repo, request: Request, project_id: str, section: str, return_to: str):
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, f"Projects - {section.title()}")

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, f"Project {project_id} not found.", "error")
        return None

    project_vendor_ids = [str(v) for v in (project.get("vendor_ids") or []) if str(v).strip()]
    requested_vendor_id = str(request.query_params.get("vendor_id", "")).strip()
    vendor_id = ""
    if requested_vendor_id and requested_vendor_id in project_vendor_ids:
        vendor_id = requested_vendor_id
    elif str(project.get("vendor_id") or "").strip() in project_vendor_ids:
        vendor_id = str(project.get("vendor_id") or "").strip()
    elif project_vendor_ids:
        vendor_id = project_vendor_ids[0]

    all_offerings = repo.list_project_offerings(None, project_id).to_dict("records")
    offerings = [row for row in all_offerings if not vendor_id or str(row.get("vendor_id") or "") == vendor_id]
    offering_ids = {str(row.get("offering_id") or "") for row in all_offerings}
    offering_owner_rows: list[dict] = []
    offering_contact_rows: list[dict] = []
    for mapped_vendor_id in project_vendor_ids:
        offering_owner_rows.extend(repo.get_vendor_offering_business_owners(mapped_vendor_id).to_dict("records"))
        offering_contact_rows.extend(repo.get_vendor_offering_contacts(mapped_vendor_id).to_dict("records"))
    linked_offering_owners = [row for row in offering_owner_rows if str(row.get("offering_id") or "") in offering_ids]
    linked_offering_contacts = [
        row for row in offering_contact_rows if str(row.get("offering_id") or "") in offering_ids
    ]
    demos = repo.list_project_demos(None, project_id).to_dict("records")
    notes = repo.list_project_notes(vendor_id or None, project_id).to_dict("records")
    docs = repo.list_docs("project", project_id).to_dict("records")
    activity = repo.get_project_activity(vendor_id or None, project_id).head(50).to_dict("records")
    project_vendors = repo.list_project_vendors(project_id).to_dict("records")
    owner_count = 1 if str(project.get("owner_principal") or "").strip() else 0

    summary = {
        "status": str(project.get("status") or "unknown"),
        "project_type": str(project.get("project_type") or "other"),
        "vendor_count": len(project_vendors),
        "offering_count": len(all_offerings),
        "demo_count": len(demos),
        "note_count": len(notes),
        "doc_count": len(docs),
        "owner_count": owner_count,
    }

    for row in demos:
        linked_demo_id = str(row.get("linked_vendor_demo_id") or "").strip()
        demo_vendor_id = str(row.get("vendor_id") or "").strip()
        row["_linked_vendor_demo_link"] = (
            f"/vendors/{demo_vendor_id}/demos?return_to={quote(f'/projects/{project_id}/demos', safe='')}"
            if linked_demo_id and demo_vendor_id
            else ""
        )

    return {
        "user": user,
        "project": project,
        "project_id": project_id,
        "vendor_id": vendor_id,
        "vendor_display_name": str(project.get("vendor_display_name") or vendor_id or "Unassigned"),
        "project_vendors": project_vendors,
        "return_to": _safe_return_to(return_to),
        "project_nav": _project_nav(project_id, _safe_return_to(return_to), section),
        "summary": summary,
        "offerings": offerings,
        "all_offerings": all_offerings,
        "offering_owners": linked_offering_owners,
        "offering_contacts": linked_offering_contacts,
        "demos": demos,
        "notes": notes,
        "docs": docs,
        "activity": activity,
    }


def _render_project_section(request: Request, base: dict, section: str):
    repo = get_repo()
    vendor_id = base["vendor_id"]
    project_id = base["project_id"]
    project = base["project"]
    vendor_demos = repo.get_vendor_demos(vendor_id).to_dict("records") if vendor_id else []
    demo_map_options = [{"demo_id": "", "label": "Select existing vendor demo"}]
    for row in vendor_demos:
        demo_id = str(row.get("demo_id") or "")
        label = f"{demo_id} | {row.get('selection_outcome') or 'unknown'} | {row.get('demo_date') or ''}"
        demo_map_options.append({"demo_id": demo_id, "label": label})

    for row in base["demos"]:
        demo_id = str(row.get("project_demo_id") or "")
        demo_vendor_id = str(row.get("vendor_id") or vendor_id or "")
        row["_update_action"] = f"/vendors/{demo_vendor_id}/projects/{project_id}/demos/{demo_id}/update"
        row["_remove_action"] = f"/vendors/{demo_vendor_id}/projects/{project_id}/demos/{demo_id}/remove"
        row["_demo_doc_link_action"] = f"/vendors/{demo_vendor_id}/projects/{project_id}/demos/{demo_id}/docs/link"
        row["_docs"] = repo.list_docs("demo", demo_id).to_dict("records")

    linked_vendor_rows: list[dict[str, str]] = []
    vendor_seen: set[str] = set()
    for row in base["project_vendors"]:
        vendor_id = str(row.get("vendor_id") or "")
        label = str(row.get("vendor_display_name") or vendor_id)
        if vendor_id and vendor_id not in vendor_seen:
            linked_vendor_rows.append({"vendor_id": vendor_id, "label": label})
            vendor_seen.add(vendor_id)
    current_offering_ids = _dedupe_ordered(
        [str(row.get("offering_id") or "") for row in base["all_offerings"] if str(row.get("offering_id") or "").strip()]
    )

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{project.get('project_name')} - {section.title()}",
        active_nav="projects",
        extra={
            "section": section,
            "project": project,
            "project_id": project_id,
            "vendor_id": vendor_id,
            "vendor_display_name": base["vendor_display_name"],
            "project_vendors": base["project_vendors"],
            "return_to": base["return_to"],
            "project_nav": base["project_nav"],
            "summary": base["summary"],
            "project_offerings": base["offerings"],
            "project_offering_owners": base["offering_owners"],
            "project_offering_contacts": base["offering_contacts"],
            "project_demos": base["demos"],
            "project_notes": base["notes"],
            "project_docs": base["docs"],
            "project_activity": base["activity"],
            "doc_source_options": repo.list_doc_source_options(),
            "demo_map_options": demo_map_options,
            "linked_vendor_rows": linked_vendor_rows,
            "current_offering_ids": current_offering_ids,
            "owner_update_action": f"/projects/{project_id}/owner/update",
            "add_vendor_action": f"/projects/{project_id}/vendors/add",
            "add_offering_action": f"/projects/{project_id}/offerings/add",
            "project_owner_change_reason_options": PROJECT_OWNER_CHANGE_REASON_OPTIONS,
            "project_association_reason_options": PROJECT_ASSOCIATION_REASON_OPTIONS,
            "project_association_auto_reason": PROJECT_ASSOCIATION_AUTO_REASON,
            "project_demo_reaudit_reason_options": PROJECT_DEMO_REAUDIT_REASON_OPTIONS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_section.html", context)




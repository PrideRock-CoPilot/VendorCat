from __future__ import annotations

from urllib.parse import quote

from fastapi import Request

from vendor_catalog_app.defaults import (
    DEFAULT_ALLOWED_RETURN_TO_PREFIXES,
    DEFAULT_RETURN_TO_PATH,
    DEFAULT_SOURCE_SYSTEM,
    DEFAULT_VENDOR_SUMMARY_MONTHS,
)
from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.routers.vendors.constants import (
    LIFECYCLE_STATES,
    OFFERING_SECTIONS,
    RISK_TIERS,
    VENDOR_SECTIONS,
)
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_user_context,
    log_page_view,
)


def _safe_return_to(value: str | None) -> str:
    if not value:
        return DEFAULT_RETURN_TO_PATH
    if any(value.startswith(prefix) for prefix in DEFAULT_ALLOWED_RETURN_TO_PREFIXES):
        return value
    return DEFAULT_RETURN_TO_PATH


def _vendor_nav(vendor_id: str, return_to: str, active_key: str) -> list[dict]:
    nav = []
    encoded_return = quote(return_to, safe="")
    for key, label in VENDOR_SECTIONS:
        nav.append(
            {
                "key": key,
                "label": label,
                "url": f"/vendors/{vendor_id}/{key}?return_to={encoded_return}",
                "active": key == active_key,
            }
        )
    return nav


def _offering_nav(vendor_id: str, offering_id: str, return_to: str, active_key: str, *, edit_mode: bool = False) -> list[dict]:
    encoded_return = quote(return_to, safe="")
    edit_query = "&edit=1" if edit_mode else ""
    out: list[dict] = []
    for key, label in OFFERING_SECTIONS:
        out.append(
            {
                "key": key,
                "label": label,
                "url": f"/vendors/{vendor_id}/offerings/{offering_id}?section={key}&return_to={encoded_return}{edit_query}",
                "active": key == active_key,
            }
        )
    return out


def _vendor_base_context(repo, request: Request, vendor_id: str, section: str, return_to: str):
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, f"Vendor 360 - {section.title()}")

    profile = repo.get_vendor_profile(vendor_id)
    if profile.empty:
        add_flash(request, f"Vendor {vendor_id} not found.", "error")
        return None

    row = profile.iloc[0].to_dict()
    display_name = str(row.get("display_name") or row.get("legal_name") or vendor_id)
    return_to = _safe_return_to(return_to)

    return {
        "user": user,
        "profile": profile,
        "profile_row": row,
        "display_name": display_name,
        "vendor_id": vendor_id,
        "return_to": return_to,
        "vendor_nav": _vendor_nav(vendor_id, return_to, section),
        "summary": repo.vendor_summary(vendor_id, months=DEFAULT_VENDOR_SUMMARY_MONTHS),
    }


def _offering_select_options(offerings: list[dict]) -> list[dict]:
    options = [{"offering_id": "", "label": "Unassigned"}]
    for offering in offerings:
        options.append(
            {
                "offering_id": str(offering.get("offering_id") or ""),
                "label": str(offering.get("offering_name") or offering.get("offering_id") or "unknown"),
            }
        )
    return options


def _project_demo_select_options(vendor_demos: list[dict]) -> list[dict]:
    options = [{"demo_id": "", "label": "Select existing vendor demo"}]
    for row in vendor_demos:
        demo_id = str(row.get("demo_id") or "")
        label = f"{demo_id} | {row.get('selection_outcome') or 'unknown'} | {row.get('demo_date') or ''}"
        options.append({"demo_id": demo_id, "label": label})
    return options


def _write_blocked(user) -> bool:
    return bool(user.config.locked_mode)


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


def _selected_project_vendor_rows(repo, vendor_ids: list[str]) -> list[dict[str, str]]:
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


def _selected_project_offering_rows(repo, offering_ids: list[str]) -> list[dict[str, str]]:
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


def _owner_org_options(repo) -> list[str]:
    return [org for org in repo.available_orgs() if org != "all"]


def _render_vendor_new_form(
    *,
    request: Request,
    user,
    repo,
    return_to: str,
    form_values: dict[str, str] | None = None,
    field_errors: dict[str, str] | None = None,
    form_error: str = "",
    status_code: int = 200,
):
    values = {
        "legal_name": "",
        "display_name": "",
        "lifecycle_state": "draft",
        "owner_org_choice": "",
        "new_owner_org_id": "",
        "risk_tier": "",
        "source_system": DEFAULT_SOURCE_SYSTEM,
    }
    if form_values:
        values.update(form_values)

    owner_org_options = _owner_org_options(repo)
    selected_owner_org = values.get("owner_org_choice", "").strip()
    typed_owner_org = values.get("new_owner_org_id", "").strip()
    if not selected_owner_org and typed_owner_org:
        selected_owner_org = "__new__"
    if selected_owner_org and selected_owner_org not in owner_org_options and selected_owner_org != "__new__":
        values["new_owner_org_id"] = selected_owner_org
        selected_owner_org = "__new__"
    values["owner_org_choice"] = selected_owner_org

    context = base_template_context(
        request=request,
        context=user,
        title="New Vendor",
        active_nav="vendors",
        extra={
            "return_to": _safe_return_to(return_to),
            "lifecycle_states": LIFECYCLE_STATES,
            "risk_tiers": RISK_TIERS,
            "owner_org_options": owner_org_options,
            "form_values": values,
            "field_errors": field_errors or {},
            "form_error": form_error,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_new.html", context, status_code=status_code)

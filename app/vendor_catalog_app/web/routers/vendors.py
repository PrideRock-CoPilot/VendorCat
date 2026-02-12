from __future__ import annotations

from urllib.parse import quote, urlencode

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID
from vendor_catalog_app.security import MAX_APPROVAL_LEVEL, MIN_CHANGE_APPROVAL_LEVEL, required_approval_level
from vendor_catalog_app.web.utils.doc_links import (
    extract_doc_fqdn,
    normalize_doc_tags,
    suggest_doc_title,
    suggest_doc_type,
)
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter(prefix="/vendors")

DEFAULT_VENDOR_FIELDS = [
    "display_name",
    "vendor_id",
    "legal_name",
    "lifecycle_state",
    "owner_org_id",
    "risk_tier",
    "updated_at",
]
DEFAULT_VENDOR_PAGE_SIZE = 25
VENDOR_PAGE_SIZES = [1, 5, 10, 25, 50, 100]
DEFAULT_VENDOR_SORT_BY = "vendor_name"
DEFAULT_VENDOR_SORT_DIR = "asc"
VENDOR_SORT_FIELDS = ["vendor_name", "vendor_id", "legal_name", "lifecycle_state", "owner_org_id", "risk_tier", "updated_at"]
VENDOR_FIELD_SORT_MAP = {
    "display_name": "vendor_name",
    "vendor_id": "vendor_id",
    "legal_name": "legal_name",
    "lifecycle_state": "lifecycle_state",
    "owner_org_id": "owner_org_id",
    "risk_tier": "risk_tier",
    "updated_at": "updated_at",
}

LIFECYCLE_STATES = ["draft", "submitted", "in_review", "approved", "active", "suspended", "retired"]
RISK_TIERS = ["low", "medium", "high", "critical"]
PROJECT_STATUSES = ["draft", "active", "blocked", "complete", "cancelled"]
PROJECT_TYPES_FALLBACK = ["rfp", "poc", "renewal", "implementation", "other"]
PROJECT_DEMO_TYPES = ["live", "recorded", "workshop", "sandbox"]
PROJECT_DEMO_OUTCOMES = ["unknown", "selected", "not_selected", "follow_up"]
OFFERING_TYPES_FALLBACK = ["SaaS", "Cloud", "PaaS", "Security", "Data", "Integration", "Other"]
OFFERING_LOB_FALLBACK = ["Enterprise", "Finance", "HR", "IT", "Operations", "Sales", "Security"]
OFFERING_SERVICE_TYPE_FALLBACK = [
    "Application",
    "Infrastructure",
    "Integration",
    "Managed Service",
    "Platform",
    "Security",
    "Support",
    "Other",
]
OFFERING_SECTIONS = [
    ("summary", "Summary"),
    ("profile", "Profile"),
    ("dataflow", "Data Flow"),
    ("ownership", "Ownership"),
    ("delivery", "Delivery"),
    ("tickets", "Tickets"),
    ("notes", "Notes"),
    ("documents", "Documents"),
]
OFFERING_TICKET_STATUSES = ["open", "in_progress", "blocked", "resolved", "closed"]
OFFERING_TICKET_PRIORITIES = ["low", "medium", "high", "critical"]
OFFERING_NOTE_TYPES = ["general", "issue", "implementation", "cost", "data_flow", "misc", "risk", "decision"]
OFFERING_DATA_METHOD_OPTIONS = ["api", "file_transfer", "cloud_to_cloud", "event_stream", "manual", "other"]

VENDOR_SECTIONS = [
    ("summary", "Summary"),
    ("ownership", "Ownership"),
    ("projects", "Projects"),
    ("offerings", "Offerings"),
    ("contracts", "Contracts"),
    ("demos", "Demos"),
    ("lineage", "Lineage/Audit"),
    ("changes", "Changes"),
]


def _safe_return_to(value: str | None) -> str:
    if not value:
        return "/vendors"
    if value.startswith("/vendors") or value.startswith("/projects"):
        return value
    return "/vendors"


def _normalize_lifecycle(value: str) -> str:
    lifecycle = value.strip().lower()
    if lifecycle not in LIFECYCLE_STATES:
        raise ValueError(f"Lifecycle state must be one of: {', '.join(LIFECYCLE_STATES)}")
    return lifecycle


def _normalize_project_status(value: str) -> str:
    status = value.strip().lower()
    if status not in PROJECT_STATUSES:
        raise ValueError(f"Project status must be one of: {', '.join(PROJECT_STATUSES)}")
    return status


def _project_type_options(repo) -> list[str]:
    options = [str(item).strip().lower() for item in repo.list_project_type_options() if str(item).strip()]
    return options or list(PROJECT_TYPES_FALLBACK)


def _offering_type_options(repo) -> list[str]:
    options = [str(item).strip() for item in repo.list_offering_type_options() if str(item).strip()]
    return options or list(OFFERING_TYPES_FALLBACK)


def _offering_lob_options(repo) -> list[str]:
    options = [str(item).strip() for item in repo.list_offering_lob_options() if str(item).strip()]
    return options or list(OFFERING_LOB_FALLBACK)


def _offering_service_type_options(repo) -> list[str]:
    options = [str(item).strip() for item in repo.list_offering_service_type_options() if str(item).strip()]
    return options or list(OFFERING_SERVICE_TYPE_FALLBACK)


def _normalize_project_type(repo, value: str) -> str:
    allowed = _project_type_options(repo)
    project_type = value.strip().lower() if value else "other"
    if project_type not in set(allowed):
        raise ValueError(f"Project type must be one of: {', '.join(allowed)}")
    return project_type


def _normalize_offering_type(repo, value: str, *, allow_blank: bool = True, extra_allowed: set[str] | None = None) -> str:
    allowed = _offering_type_options(repo)
    offering_type = (value or "").strip()
    if not offering_type:
        return "" if allow_blank else allowed[0]
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(offering_type.lower())
    if canonical:
        return canonical
    if extra_allowed and offering_type in extra_allowed:
        return offering_type
    raise ValueError(f"Offering type must be one of: {', '.join(allowed)}")


def _normalize_offering_lob(repo, value: str, *, allow_blank: bool = True, extra_allowed: set[str] | None = None) -> str:
    allowed = _offering_lob_options(repo)
    lob = (value or "").strip()
    if not lob:
        return "" if allow_blank else allowed[0]
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(lob.lower())
    if canonical:
        return canonical
    if extra_allowed and lob in extra_allowed:
        return lob
    raise ValueError(f"LOB must be one of: {', '.join(allowed)}")


def _normalize_offering_service_type(
    repo,
    value: str,
    *,
    allow_blank: bool = True,
    extra_allowed: set[str] | None = None,
) -> str:
    allowed = _offering_service_type_options(repo)
    service_type = (value or "").strip()
    if not service_type:
        return "" if allow_blank else allowed[0]
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(service_type.lower())
    if canonical:
        return canonical
    if extra_allowed and service_type in extra_allowed:
        return service_type
    raise ValueError(f"Service type must be one of: {', '.join(allowed)}")


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


def _load_visible_fields(repo, user_principal: str, available_fields: list[str]) -> list[str]:
    saved = repo.get_user_setting(user_principal, "vendor360_list")
    saved_fields = saved.get("visible_fields") if isinstance(saved, dict) else None
    if not isinstance(saved_fields, list) or not saved_fields:
        saved_fields = DEFAULT_VENDOR_FIELDS
    visible = [field for field in saved_fields if field in available_fields]
    return visible or available_fields


def _merge_vendor360_settings(repo, user_principal: str, updates: dict) -> dict:
    saved = repo.get_user_setting(user_principal, "vendor360_list")
    merged = dict(saved) if isinstance(saved, dict) else {}
    merged.update(updates)
    repo.save_user_setting(user_principal=user_principal, setting_key="vendor360_list", setting_value=merged)
    return merged


def _normalize_vendor_sort(sort_by: str, sort_dir: str) -> tuple[str, str]:
    normalized_sort_by = (sort_by or DEFAULT_VENDOR_SORT_BY).strip().lower()
    if normalized_sort_by not in VENDOR_SORT_FIELDS:
        normalized_sort_by = DEFAULT_VENDOR_SORT_BY
    normalized_sort_dir = "desc" if (sort_dir or "").strip().lower() == "desc" else "asc"
    return normalized_sort_by, normalized_sort_dir


def _normalize_vendor_page(page: int, page_size: int) -> tuple[int, int]:
    normalized_page_size = page_size if page_size in VENDOR_PAGE_SIZES else DEFAULT_VENDOR_PAGE_SIZE
    normalized_page = max(1, int(page or 1))
    return normalized_page, normalized_page_size


def _vendor_list_url(
    *,
    q: str,
    status: str,
    owner: str,
    risk: str,
    group: str,
    page: int,
    page_size: int,
    sort_by: str,
    sort_dir: str,
    show_settings: int,
) -> str:
    return "/vendors?" + urlencode(
        {
            "q": q,
            "status": status,
            "owner": owner,
            "risk": risk,
            "group": group,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "show_settings": show_settings,
        }
    )


def _series_with_bar_pct(rows: list[dict], value_key: str) -> list[dict]:
    if not rows:
        return rows
    max_value = max(float(row.get(value_key, 0) or 0) for row in rows)
    for row in rows:
        value = float(row.get(value_key, 0) or 0)
        row["bar_pct"] = int((value / max_value) * 100) if max_value > 0 else 0
    return rows


def _build_line_chart_points(
    rows: list[dict], x_key: str, y_key: str, width: int = 560, height: int = 180, pad: int = 20
) -> tuple[str, list[dict]]:
    if not rows:
        return "", rows
    cleaned = [{"x": str(row.get(x_key, "")), "y": float(row.get(y_key, 0) or 0)} for row in rows]
    if len(cleaned) == 1:
        cleaned = cleaned + [dict(cleaned[0])]

    values = [item["y"] for item in cleaned]
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1.0)
    points = []
    n = len(cleaned)
    for idx, item in enumerate(cleaned):
        x = pad + ((width - (pad * 2)) * (idx / (n - 1)))
        y = height - pad - ((height - (pad * 2)) * ((item["y"] - min_v) / span))
        points.append(f"{x:.1f},{y:.1f}")
        item["plot_x"] = x
        item["plot_y"] = y
    return " ".join(points), cleaned


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
        "summary": repo.vendor_summary(vendor_id, months=12),
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
        "source_system": "manual",
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


@router.get("")
def vendor_list(
    request: Request,
    q: str = "",
    search: str = "",
    status: str = "all",
    owner: str = "all",
    risk: str = "all",
    group: str = "none",
    page: int = 1,
    page_size: int = DEFAULT_VENDOR_PAGE_SIZE,
    sort_by: str = DEFAULT_VENDOR_SORT_BY,
    sort_dir: str = DEFAULT_VENDOR_SORT_DIR,
    show_settings: int = 0,
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor 360")

    saved_settings = repo.get_user_setting(user.user_principal, "vendor360_list")
    saved_prefs = saved_settings.get("list_prefs", {}) if isinstance(saved_settings, dict) else {}
    qp = request.query_params

    if "q" in qp:
        resolved_q = q.strip()
    elif "search" in qp:
        resolved_q = search.strip()
    else:
        resolved_q = str(saved_prefs.get("q", "")).strip()

    if "status" not in qp and str(saved_prefs.get("status", "")).strip():
        status = str(saved_prefs.get("status", "all"))
    if status not in ["all"] + LIFECYCLE_STATES:
        status = "all"

    if "owner" not in qp and str(saved_prefs.get("owner", "")).strip():
        owner = str(saved_prefs.get("owner", "all"))
    if owner != "all" and owner not in repo.available_orgs():
        owner = "all"

    if "risk" not in qp and str(saved_prefs.get("risk", "")).strip():
        risk = str(saved_prefs.get("risk", "all"))
    if risk != "all" and risk not in RISK_TIERS:
        risk = "all"

    if "group" not in qp and str(saved_prefs.get("group", "")).strip():
        group = str(saved_prefs.get("group", "none"))

    if "sort_by" not in qp and str(saved_prefs.get("sort_by", "")).strip():
        sort_by = str(saved_prefs.get("sort_by", DEFAULT_VENDOR_SORT_BY))
    if "sort_dir" not in qp and str(saved_prefs.get("sort_dir", "")).strip():
        sort_dir = str(saved_prefs.get("sort_dir", DEFAULT_VENDOR_SORT_DIR))
    sort_by, sort_dir = _normalize_vendor_sort(sort_by, sort_dir)

    if "page_size" not in qp and saved_prefs.get("page_size"):
        try:
            page_size = int(saved_prefs.get("page_size"))
        except Exception:
            page_size = DEFAULT_VENDOR_PAGE_SIZE
    page, page_size = _normalize_vendor_page(page, page_size)

    vendors_df, total_rows = repo.list_vendors_page(
        search_text=resolved_q,
        lifecycle_state=status,
        owner_org_id=owner,
        risk_tier=risk,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    vendors_df = vendors_df.reset_index(drop=True)

    available_fields = vendors_df.columns.tolist() if not vendors_df.empty else DEFAULT_VENDOR_FIELDS
    visible_fields = _load_visible_fields(repo, user.user_principal, available_fields)

    grouped = pd.DataFrame()
    if group != "none" and group in vendors_df.columns and not vendors_df.empty:
        grouped = (
            vendors_df.groupby(group, dropna=False, as_index=False)
            .agg(vendor_count=("vendor_id", "count"))
            .sort_values("vendor_count", ascending=False)
        )

    owner_options = repo.available_orgs()
    risk_options = ["all"] + RISK_TIERS

    group_options = ["none"] + [
        c for c in ["lifecycle_state", "owner_org_id", "risk_tier", "source_system"] if c in DEFAULT_VENDOR_FIELDS or c in available_fields
    ]
    return_to = _vendor_list_url(
        q=resolved_q,
        status=status,
        owner=owner,
        risk=risk,
        group=group,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        show_settings=show_settings,
    )

    offering_map: dict[str, list[dict]] = {}
    vendor_ids = vendors_df["vendor_id"].astype(str).tolist() if "vendor_id" in vendors_df.columns else []
    offering_rows = repo.list_vendor_offerings_for_vendors(vendor_ids).to_dict("records")
    for row in offering_rows:
        vid = str(row.get("vendor_id") or "")
        if vid not in offering_map:
            offering_map[vid] = []
        offering_map[vid].append(
            {
                "offering_id": str(row.get("offering_id") or ""),
                "offering_name": str(row.get("offering_name") or row.get("offering_id") or ""),
                "lifecycle_state": str(row.get("lifecycle_state") or ""),
            }
        )

    vendor_rows = vendors_df.to_dict("records")
    for row in vendor_rows:
        vid = str(row.get("vendor_id"))
        row["_vendor_link"] = f"/vendors/{vid}/summary?return_to={quote(return_to, safe='')}"
        row["_offerings_page_link"] = f"/vendors/{vid}/offerings?return_to={quote(return_to, safe='')}"
        row["_offerings"] = []
        for offering in offering_map.get(vid, []):
            entry = dict(offering)
            entry["_offering_link"] = (
                f"/vendors/{vid}/offerings/{entry.get('offering_id')}?return_to={quote(return_to, safe='')}"
            )
            row["_offerings"].append(entry)

    page_count = max(1, (int(total_rows) + page_size - 1) // page_size)
    if page > page_count:
        page = page_count
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1 if page < page_count else page_count
    sort_links: dict[str, str] = {}
    for field in visible_fields:
        mapped_sort = VENDOR_FIELD_SORT_MAP.get(field)
        if not mapped_sort:
            continue
        next_dir = "desc" if sort_by == mapped_sort and sort_dir == "asc" else "asc"
        sort_links[field] = _vendor_list_url(
            q=resolved_q,
            status=status,
            owner=owner,
            risk=risk,
            group=group,
            page=1,
            page_size=page_size,
            sort_by=mapped_sort,
            sort_dir=next_dir,
            show_settings=show_settings,
        )

    _merge_vendor360_settings(
        repo,
        user.user_principal,
        {
            "list_prefs": {
                "q": resolved_q,
                "status": status,
                "owner": owner,
                "risk": risk,
                "group": group,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            }
        },
    )

    context = base_template_context(
        request=request,
        context=user,
        title="Vendor 360",
        active_nav="vendors",
        extra={
            "filters": {
                "q": resolved_q,
                "search": resolved_q,
                "status": status,
                "owner": owner,
                "risk": risk,
                "group": group,
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            },
            "status_options": ["all"] + LIFECYCLE_STATES,
            "owner_options": owner_options,
            "risk_options": risk_options,
            "group_options": group_options,
            "grouped": grouped.to_dict("records"),
            "show_settings": bool(show_settings),
            "page_sizes": VENDOR_PAGE_SIZES,
            "all_fields": available_fields,
            "visible_fields": visible_fields,
            "sort_links": sort_links,
            "vendors": vendor_rows,
            "total_rows": int(total_rows),
            "page_count": page_count,
            "show_from": ((page - 1) * page_size + 1) if total_rows else 0,
            "show_to": min(page * page_size, int(total_rows)),
            "prev_page_url": _vendor_list_url(
                q=resolved_q,
                status=status,
                owner=owner,
                risk=risk,
                group=group,
                page=prev_page,
                page_size=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
                show_settings=show_settings,
            ),
            "next_page_url": _vendor_list_url(
                q=resolved_q,
                status=status,
                owner=owner,
                risk=risk,
                group=group,
                page=next_page,
                page_size=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
                show_settings=show_settings,
            ),
            "settings_toggle_url": _vendor_list_url(
                q=resolved_q,
                status=status,
                owner=owner,
                risk=risk,
                group=group,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
                show_settings=0 if show_settings else 1,
            ),
            "return_to": return_to,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendors_list.html", context)


@router.post("/settings")
async def vendor_settings(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    field_names = [str(x) for x in form.getlist("field_name")]
    selected: list[tuple[int, str]] = []
    for field in field_names:
        if form.get(f"include_{field}") != "on":
            continue
        order_raw = str(form.get(f"order_{field}", "999"))
        try:
            order_num = int(order_raw)
        except ValueError:
            order_num = 999
        selected.append((order_num, field))
    selected.sort(key=lambda t: t[0])
    visible_fields = [field for _, field in selected]
    if not visible_fields:
        visible_fields = [field for field in DEFAULT_VENDOR_FIELDS if field in field_names] or field_names

    _merge_vendor360_settings(repo, user.user_principal, {"visible_fields": visible_fields})
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="vendor_360",
        event_type="update_field_matrix",
        payload={"field_count": len(visible_fields)},
    )
    add_flash(request, "Vendor list fields updated.", "success")
    return RedirectResponse(url=return_to, status_code=303)


@router.get("/new")
def vendor_new_form(request: Request, return_to: str = "/vendors"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor Create")

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create vendors.", "error")
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    return _render_vendor_new_form(
        request=request,
        user=user,
        repo=repo,
        return_to=return_to,
    )


@router.post("/new")
async def vendor_new_submit(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create vendors.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    form_values = {
        "legal_name": str(form.get("legal_name", "")).strip(),
        "display_name": str(form.get("display_name", "")).strip(),
        "lifecycle_state": str(form.get("lifecycle_state", "draft")).strip().lower(),
        "owner_org_choice": str(form.get("owner_org_choice", "")).strip(),
        "new_owner_org_id": str(form.get("new_owner_org_id", "")).strip(),
        "risk_tier": str(form.get("risk_tier", "")).strip().lower(),
        "source_system": str(form.get("source_system", "manual")).strip(),
    }
    legacy_owner_org_id = str(form.get("owner_org_id", "")).strip()
    if legacy_owner_org_id and not form_values["owner_org_choice"] and not form_values["new_owner_org_id"]:
        form_values["owner_org_choice"] = legacy_owner_org_id
    owner_org_id = ""
    if form_values["owner_org_choice"] and form_values["owner_org_choice"] != "__new__":
        owner_org_id = form_values["owner_org_choice"]
    elif form_values["owner_org_choice"] == "__new__":
        owner_org_id = form_values["new_owner_org_id"]

    field_errors: dict[str, str] = {}
    if not form_values["legal_name"]:
        field_errors["legal_name"] = "Legal name is required."
    if not owner_org_id:
        if form_values["owner_org_choice"] == "__new__":
            field_errors["new_owner_org_id"] = "Enter a new Owner Org ID."
        else:
            field_errors["owner_org_choice"] = "Owner Org ID is required."

    try:
        form_values["lifecycle_state"] = _normalize_lifecycle(form_values["lifecycle_state"])
        if form_values["risk_tier"] and form_values["risk_tier"] not in RISK_TIERS:
            raise ValueError(f"Risk tier must be one of: {', '.join(RISK_TIERS)}")
    except Exception as exc:
        field_errors["lifecycle_state"] = str(exc)

    if field_errors:
        add_flash(request, "Please fix the highlighted fields.", "error")
        return _render_vendor_new_form(
            request=request,
            user=user,
            repo=repo,
            return_to=return_to,
            form_values=form_values,
            field_errors=field_errors,
            form_error="Validation failed.",
            status_code=400,
        )

    try:
        if user.can_apply_change("create_vendor_profile"):
            vendor_id = repo.create_vendor_profile(
                actor_user_principal=user.user_principal,
                legal_name=form_values["legal_name"],
                display_name=form_values["display_name"] or form_values["legal_name"],
                lifecycle_state=form_values["lifecycle_state"],
                owner_org_id=owner_org_id,
                risk_tier=form_values["risk_tier"] or None,
                source_system=form_values["source_system"] or "manual",
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_360",
                event_type="vendor_create",
                payload={"vendor_id": vendor_id},
            )
            add_flash(request, f"Vendor created: {vendor_id}", "success")
            return RedirectResponse(
                url=f"/vendors/{vendor_id}/summary?return_to={quote(return_to, safe='')}",
                status_code=303,
            )
        request_id = repo.create_vendor_change_request(
            vendor_id=GLOBAL_CHANGE_VENDOR_ID,
            requestor_user_principal=user.user_principal,
            change_type="create_vendor_profile",
            payload={
                "legal_name": form_values["legal_name"],
                "display_name": form_values["display_name"] or form_values["legal_name"],
                "lifecycle_state": form_values["lifecycle_state"],
                "owner_org_id": owner_org_id,
                "risk_tier": form_values["risk_tier"] or None,
                "source_system": form_values["source_system"] or "manual",
            },
        )
        add_flash(request, f"Pending change request submitted: {request_id}", "success")
        return RedirectResponse(url="/workflows?status=pending", status_code=303)
    except Exception as exc:
        error_text = str(exc)
        if "owner_org_id" in error_text.lower():
            field_errors["owner_org_choice"] = "Owner Org ID is required."
            if form_values["owner_org_choice"] == "__new__":
                field_errors["new_owner_org_id"] = "Owner Org ID is required."
        add_flash(request, "Could not create vendor. Fix the highlighted fields and try again.", "error")
        return _render_vendor_new_form(
            request=request,
            user=user,
            repo=repo,
            return_to=return_to,
            form_values=form_values,
            field_errors=field_errors,
            form_error=error_text,
            status_code=400,
        )


@router.get("/{vendor_id}")
def vendor_default(request: Request, vendor_id: str, return_to: str = "/vendors"):
    return RedirectResponse(
        url=f"/vendors/{vendor_id}/summary?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )


@router.get("/{vendor_id}/summary")
def vendor_summary_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "summary", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    profile_row = base["profile_row"]
    contacts = repo.get_vendor_contacts(vendor_id).to_dict("records")
    top_contacts = contacts[:3]
    top_offerings = repo.get_vendor_offerings(vendor_id).head(5).to_dict("records")
    for row in top_offerings:
        row["_offering_link"] = (
            f"/vendors/{vendor_id}/offerings/{row.get('offering_id')}?return_to={quote(base['return_to'], safe='')}"
        )
    projects_df = repo.list_projects(vendor_id)
    if "status" in projects_df.columns:
        active_projects = projects_df[projects_df["status"].astype(str).str.lower() == "active"]
        projects_preview = (active_projects if not active_projects.empty else projects_df).head(5).to_dict("records")
    else:
        projects_preview = projects_df.head(5).to_dict("records")
    for row in projects_preview:
        row["_project_link"] = (
            f"/vendors/{vendor_id}/projects/{row.get('project_id')}?return_to={quote(base['return_to'], safe='')}"
        )
    docs_preview = repo.list_docs("vendor", vendor_id).head(5).to_dict("records")

    spend_category = _series_with_bar_pct(
        repo.vendor_spend_by_category(vendor_id, months=12).to_dict("records"),
        "total_spend",
    )
    spend_trend_rows = repo.vendor_monthly_spend_trend(vendor_id, months=12).to_dict("records")
    trend_points, spend_trend_plot_rows = _build_line_chart_points(spend_trend_rows, "month", "total_spend")
    raw_fields = [{"field": key, "value": value} for key, value in profile_row.items()]

    key_facts = {
        "legal_name": profile_row.get("legal_name"),
        "display_name": profile_row.get("display_name"),
        "vendor_id": profile_row.get("vendor_id"),
        "owner_org_id": profile_row.get("owner_org_id"),
        "source_system": profile_row.get("source_system"),
        "active_lobs": ", ".join(base["summary"].get("active_lob_values") or []) or "-",
        "active_service_types": ", ".join(base["summary"].get("active_service_type_values") or []) or "-",
        "updated_at": profile_row.get("updated_at"),
    }

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Summary",
        active_nav="vendors",
        extra={
            "section": "summary",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "key_facts": key_facts,
            "top_contacts": top_contacts,
            "top_offerings": top_offerings,
            "offerings_page_link": f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}",
            "projects_preview": projects_preview,
            "projects_page_link": f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            "docs_preview": docs_preview,
            "doc_source_options": repo.list_doc_source_options(),
            "spend_category": spend_category,
            "spend_trend_points": trend_points,
            "spend_trend_plot_rows": spend_trend_plot_rows,
            "raw_fields": raw_fields,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/ownership")
def vendor_ownership_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "ownership", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Ownership",
        active_nav="vendors",
        extra={
            "section": "ownership",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "owners": repo.get_vendor_business_owners(vendor_id).to_dict("records"),
            "org_assignments": repo.get_vendor_org_assignments(vendor_id).to_dict("records"),
            "contacts": repo.get_vendor_contacts(vendor_id).to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/owners/add")
async def add_vendor_owner_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "owner_user_principal": owner_user_principal,
            "owner_role": owner_role,
            "reason": reason,
        }
        if user.can_apply_change("add_vendor_owner"):
            owner_id = repo.add_vendor_owner(
                vendor_id=vendor_id,
                owner_user_principal=owner_user_principal,
                owner_role=owner_role,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Vendor owner added: {owner_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_vendor_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="add_vendor_owner",
            payload={"vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add vendor owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/org-assignments/add")
async def add_vendor_org_assignment_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    org_id = str(form.get("org_id", "")).strip()
    assignment_type = str(form.get("assignment_type", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"org_id": org_id, "assignment_type": assignment_type, "reason": reason}
        if user.can_apply_change("add_vendor_org_assignment"):
            assignment_id = repo.add_vendor_org_assignment(
                vendor_id=vendor_id,
                org_id=org_id,
                assignment_type=assignment_type,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Org assignment added: {assignment_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_vendor_org_assignment",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="add_vendor_org_assignment",
            payload={"vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add org assignment: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/contacts/add")
async def add_vendor_contact_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    full_name = str(form.get("full_name", "")).strip()
    contact_type = str(form.get("contact_type", "")).strip()
    email = str(form.get("email", "")).strip()
    phone = str(form.get("phone", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "full_name": full_name,
            "contact_type": contact_type,
            "email": email or None,
            "phone": phone or None,
            "reason": reason,
        }
        if user.can_apply_change("add_vendor_contact"):
            contact_id = repo.add_vendor_contact(
                vendor_id=vendor_id,
                full_name=full_name,
                contact_type=contact_type,
                email=email or None,
                phone=phone or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Vendor contact added: {contact_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_vendor_contact",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="add_vendor_contact",
            payload={"vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add vendor contact: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.get("/{vendor_id}/portfolio")
def vendor_portfolio_compat(request: Request, vendor_id: str, return_to: str = "/vendors"):
    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )


@router.get("/{vendor_id}/offerings")
def vendor_offerings_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "offerings", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    offerings = repo.get_vendor_offerings(vendor_id).to_dict("records")
    contracts = repo.get_vendor_contracts(vendor_id).to_dict("records")
    demos = repo.get_vendor_demos(vendor_id).to_dict("records")
    owners = repo.get_vendor_offering_business_owners(vendor_id).to_dict("records")
    contacts = repo.get_vendor_offering_contacts(vendor_id).to_dict("records")

    contract_count: dict[str, int] = {}
    demo_count: dict[str, int] = {}
    owner_count: dict[str, int] = {}
    contact_count: dict[str, int] = {}
    for row in contracts:
        key = str(row.get("offering_id") or "")
        contract_count[key] = contract_count.get(key, 0) + 1
    for row in demos:
        key = str(row.get("offering_id") or "")
        demo_count[key] = demo_count.get(key, 0) + 1
    for row in owners:
        key = str(row.get("offering_id") or "")
        owner_count[key] = owner_count.get(key, 0) + 1
    for row in contacts:
        key = str(row.get("offering_id") or "")
        contact_count[key] = contact_count.get(key, 0) + 1

    for row in offerings:
        off_id = str(row.get("offering_id") or "")
        row["_open_link"] = f"/vendors/{vendor_id}/offerings/{off_id}?return_to={quote(base['return_to'], safe='')}"
        row["_edit_link"] = (
            f"/vendors/{vendor_id}/offerings/{off_id}?edit=1&return_to={quote(base['return_to'], safe='')}"
        )
        row["doc_count"] = int(len(repo.list_docs("offering", off_id)))
        row["contract_count"] = contract_count.get(off_id, 0)
        row["demo_count"] = demo_count.get(off_id, 0)
        row["owner_count"] = owner_count.get(off_id, 0)
        row["contact_count"] = contact_count.get(off_id, 0)

    offering_options = _offering_select_options(offerings)
    unassigned_contracts = repo.get_unassigned_contracts(vendor_id).to_dict("records")
    unassigned_demos = repo.get_unassigned_demos(vendor_id).to_dict("records")
    offerings_return_to = f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}"

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Offerings",
        active_nav="vendors",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "summary": base["summary"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "offerings": offerings,
            "offering_options": offering_options,
            "unassigned_contracts": unassigned_contracts,
            "unassigned_demos": unassigned_demos,
            "offerings_return_to": offerings_return_to,
            "doc_source_options": repo.list_doc_source_options(),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_offerings.html", context)


@router.get("/{vendor_id}/offerings/new")
def offering_new_form(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "offerings", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to create offerings.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - New Offering",
        active_nav="vendors",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "lifecycle_states": LIFECYCLE_STATES,
            "criticality_tiers": ["tier_1", "tier_2", "tier_3", "tier_4"],
            "offering_types": _offering_type_options(repo),
            "offering_lob_options": _offering_lob_options(repo),
            "offering_service_type_options": _offering_service_type_options(repo),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "offering_new.html", context)


@router.post("/{vendor_id}/offerings/new")
async def offering_new_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create offerings.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    offering_name = str(form.get("offering_name", "")).strip()
    offering_type = str(form.get("offering_type", "")).strip()
    lob = str(form.get("lob", "")).strip()
    service_type = str(form.get("service_type", "")).strip()
    lifecycle_state = str(form.get("lifecycle_state", "draft")).strip().lower()
    criticality_tier = str(form.get("criticality_tier", "")).strip()

    try:
        lifecycle_state = _normalize_lifecycle(lifecycle_state)
        offering_type = _normalize_offering_type(repo, offering_type)
        lob = _normalize_offering_lob(repo, lob)
        service_type = _normalize_offering_service_type(repo, service_type)
        if user.can_apply_change("create_offering"):
            offering_id = repo.create_offering(
                vendor_id=vendor_id,
                actor_user_principal=user.user_principal,
                offering_name=offering_name,
                offering_type=offering_type or None,
                lob=lob or None,
                service_type=service_type or None,
                lifecycle_state=lifecycle_state,
                criticality_tier=criticality_tier or None,
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_offerings",
                event_type="offering_create",
                payload={"vendor_id": vendor_id, "offering_id": offering_id},
            )
            add_flash(request, f"Offering created: {offering_id}", "success")
            return RedirectResponse(
                url=f"/vendors/{vendor_id}/offerings/{offering_id}?return_to={quote(return_to, safe='')}",
                status_code=303,
            )
        request_id = repo.create_vendor_change_request(
            vendor_id=_request_scope_vendor_id(vendor_id),
            requestor_user_principal=user.user_principal,
            change_type="create_offering",
            payload={
                "vendor_id": vendor_id,
                "offering_name": offering_name,
                "offering_type": offering_type or None,
                "lob": lob or None,
                "service_type": service_type or None,
                "lifecycle_state": lifecycle_state,
                "criticality_tier": criticality_tier or None,
            },
        )
        add_flash(request, f"Pending change request submitted: {request_id}", "success")
        return RedirectResponse(url="/workflows?status=pending", status_code=303)
    except Exception as exc:
        add_flash(request, f"Could not create offering: {exc}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/new?return_to={quote(return_to, safe='')}",
            status_code=303,
        )


@router.get("/{vendor_id}/offerings/{offering_id}")
def offering_detail_page(
    request: Request,
    vendor_id: str,
    offering_id: str,
    return_to: str = "/vendors",
    section: str = "summary",
    edit: int = 0,
    edit_data_flow_id: str = "",
    new_data_feed: int = 0,
):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "offerings", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    offering = repo.get_offering_record(vendor_id, offering_id)
    if offering is None:
        add_flash(request, f"Offering {offering_id} not found for vendor.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    owners_df = repo.get_vendor_offering_business_owners(vendor_id)
    contacts_df = repo.get_vendor_offering_contacts(vendor_id)
    contracts_df = repo.get_vendor_contracts(vendor_id)
    demos_df = repo.get_vendor_demos(vendor_id)
    vendor_offerings = repo.get_vendor_offerings(vendor_id).to_dict("records")
    offering_options = _offering_select_options(vendor_offerings)

    current_contracts = contracts_df[contracts_df["offering_id"].astype(str) == str(offering_id)].to_dict("records")
    current_demos = demos_df[demos_df["offering_id"].astype(str) == str(offering_id)].to_dict("records")
    offering_docs = repo.list_docs("offering", offering_id).to_dict("records")
    try:
        offering_profile = repo.get_offering_profile(vendor_id, offering_id)
        offering_data_flows = repo.list_offering_data_flows(vendor_id, offering_id).to_dict("records")
        offering_tickets = repo.list_offering_tickets(vendor_id, offering_id).to_dict("records")
        offering_notes = repo.list_offering_notes(offering_id).to_dict("records")
        offering_activity = repo.get_offering_activity(vendor_id, offering_id).head(50).to_dict("records")
    except Exception as exc:
        add_flash(
            request,
            (
                "Offering operations tables are not available. Run setup/databricks/001_create_databricks_schema.sql "
                f"for this Databricks schema. Details: {exc}"
            ),
            "error",
        )
        offering_profile = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "estimated_monthly_cost": None,
            "implementation_notes": None,
            "data_sent": None,
            "data_received": None,
            "integration_method": None,
            "inbound_method": None,
            "inbound_landing_zone": None,
            "inbound_identifiers": None,
            "inbound_reporting_layer": None,
            "inbound_ingestion_notes": None,
            "outbound_method": None,
            "outbound_creation_process": None,
            "outbound_delivery_process": None,
            "outbound_responsible_owner": None,
            "outbound_notes": None,
            "updated_at": None,
            "updated_by": None,
        }
        offering_data_flows = []
        offering_tickets = []
        offering_notes = []
        offering_activity = []
    inbound_data_flows = [
        row for row in offering_data_flows if str(row.get("direction", "")).strip().lower() == "inbound"
    ]
    outbound_data_flows = [
        row for row in offering_data_flows if str(row.get("direction", "")).strip().lower() == "outbound"
    ]
    owner_options = repo.search_user_directory(limit=250).to_dict("records")

    section_key = (section or "summary").strip().lower()
    valid_sections = {item[0] for item in OFFERING_SECTIONS}
    if section_key not in valid_sections:
        section_key = "summary"
    if edit and section_key == "summary":
        section_key = "profile"
    edit_data_flow_id = str(edit_data_flow_id or "").strip()
    selected_data_flow: dict[str, object] | None = None
    if section_key == "dataflow" and edit_data_flow_id:
        try:
            selected_data_flow = repo.get_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                data_flow_id=edit_data_flow_id,
            )
        except Exception:
            selected_data_flow = None

    data_feed_form = {
        "direction": "inbound",
        "flow_name": "",
        "method": "",
        "data_description": "",
        "endpoint_details": "",
        "identifiers": "",
        "reporting_layer": "",
        "creation_process": "",
        "delivery_process": "",
        "owner_user_principal": "",
        "notes": "",
        "reason": "",
    }
    if selected_data_flow:
        data_feed_form.update(
            {
                "direction": str(selected_data_flow.get("direction") or "inbound"),
                "flow_name": str(selected_data_flow.get("flow_name") or ""),
                "method": str(selected_data_flow.get("method") or ""),
                "data_description": str(selected_data_flow.get("data_description") or ""),
                "endpoint_details": str(selected_data_flow.get("endpoint_details") or ""),
                "identifiers": str(selected_data_flow.get("identifiers") or ""),
                "reporting_layer": str(selected_data_flow.get("reporting_layer") or ""),
                "creation_process": str(selected_data_flow.get("creation_process") or ""),
                "delivery_process": str(selected_data_flow.get("delivery_process") or ""),
                "owner_user_principal": str(selected_data_flow.get("owner_user_principal") or ""),
                "notes": str(selected_data_flow.get("notes") or ""),
            }
        )
    show_data_feed_editor = bool(section_key == "dataflow" and (selected_data_flow or new_data_feed))

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - {offering.get('offering_name', offering_id)}",
        active_nav="vendors",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "summary": base["summary"],
            "vendor_nav": base["vendor_nav"],
            "offering": offering,
            "offering_options": offering_options,
            "return_to": base["return_to"],
            "portfolio_back": f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}",
            "offering_owners": owners_df[owners_df["offering_id"].astype(str) == str(offering_id)].to_dict("records"),
            "offering_contacts": contacts_df[contacts_df["offering_id"].astype(str) == str(offering_id)].to_dict("records"),
            "offering_contracts": current_contracts,
            "offering_demos": current_demos,
            "offering_docs": offering_docs,
            "offering_profile": offering_profile,
            "offering_data_flows": offering_data_flows,
            "inbound_data_flows": inbound_data_flows,
            "outbound_data_flows": outbound_data_flows,
            "offering_tickets": offering_tickets,
            "offering_notes": offering_notes,
            "offering_activity": offering_activity,
            "offering_owner_options": owner_options,
            "section": section_key,
            "offering_nav": _offering_nav(vendor_id, offering_id, base["return_to"], section_key, edit_mode=bool(edit)),
            "recent_offering_notes": offering_notes[:5],
            "recent_offering_tickets": offering_tickets[:5],
            "edit_mode": bool(edit),
            "lifecycle_states": LIFECYCLE_STATES,
            "criticality_tiers": ["tier_1", "tier_2", "tier_3", "tier_4"],
            "offering_types": _offering_type_options(repo),
            "offering_lob_options": _offering_lob_options(repo),
            "offering_service_type_options": _offering_service_type_options(repo),
            "offering_ticket_statuses": OFFERING_TICKET_STATUSES,
            "offering_ticket_priorities": OFFERING_TICKET_PRIORITIES,
            "offering_note_types": OFFERING_NOTE_TYPES,
            "offering_data_method_options": OFFERING_DATA_METHOD_OPTIONS,
            "doc_source_options": repo.list_doc_source_options(),
            "selected_data_flow": selected_data_flow,
            "data_feed_form": data_feed_form,
            "show_data_feed_editor": show_data_feed_editor,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "offering_detail.html", context)


@router.post("/{vendor_id}/offerings/{offering_id}/update")
async def offering_update_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings/{offering_id}?return_to={quote(return_to, safe='')}", status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings/{offering_id}?return_to={quote(return_to, safe='')}", status_code=303)

    current_offering = repo.get_offering_record(vendor_id, offering_id)
    if current_offering is None:
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)

    updates = {
        "offering_name": str(form.get("offering_name", "")).strip(),
        "offering_type": str(form.get("offering_type", "")).strip(),
        "lob": str(form.get("lob", "")).strip(),
        "service_type": str(form.get("service_type", "")).strip(),
        "lifecycle_state": str(form.get("lifecycle_state", "")).strip().lower(),
        "criticality_tier": str(form.get("criticality_tier", "")).strip(),
    }

    try:
        if updates["lifecycle_state"]:
            updates["lifecycle_state"] = _normalize_lifecycle(updates["lifecycle_state"])
        existing_type = str(current_offering.get("offering_type") or "").strip()
        updates["offering_type"] = _normalize_offering_type(
            repo,
            updates["offering_type"],
            extra_allowed={existing_type} if existing_type else None,
        )
        updates["offering_type"] = updates["offering_type"] or None
        existing_lob = str(current_offering.get("lob") or "").strip()
        updates["lob"] = _normalize_offering_lob(
            repo,
            updates["lob"],
            extra_allowed={existing_lob} if existing_lob else None,
        )
        updates["lob"] = updates["lob"] or None
        existing_service_type = str(current_offering.get("service_type") or "").strip()
        updates["service_type"] = _normalize_offering_service_type(
            repo,
            updates["service_type"],
            extra_allowed={existing_service_type} if existing_service_type else None,
        )
        updates["service_type"] = updates["service_type"] or None
        if not updates["offering_name"]:
            raise ValueError("Offering name is required.")
        payload = {"offering_id": offering_id, "updates": updates, "reason": reason}
        if user.can_apply_change("update_offering"):
            result = repo.update_offering_fields(
                vendor_id=vendor_id,
                offering_id=offering_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Offering updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=profile&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/profile/save")
async def offering_profile_save_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    source_section = str(form.get("source_section", "profile")).strip().lower()
    if source_section not in {"profile", "dataflow"}:
        source_section = "profile"
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)

    updates: dict[str, str | float | None] = {}
    if "estimated_monthly_cost" in form:
        raw_cost = str(form.get("estimated_monthly_cost", "")).strip()
        if raw_cost:
            try:
                updates["estimated_monthly_cost"] = float(raw_cost.replace(",", ""))
            except Exception:
                add_flash(request, "Estimated monthly cost must be numeric.", "error")
                return RedirectResponse(
                    url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
                    status_code=303,
                )
        else:
            updates["estimated_monthly_cost"] = None
    if "implementation_notes" in form:
        updates["implementation_notes"] = str(form.get("implementation_notes", "")).strip() or None
    if "data_sent" in form:
        updates["data_sent"] = str(form.get("data_sent", "")).strip() or None
    if "data_received" in form:
        updates["data_received"] = str(form.get("data_received", "")).strip() or None
    if "integration_method" in form:
        updates["integration_method"] = str(form.get("integration_method", "")).strip() or None
    if "inbound_method" in form:
        updates["inbound_method"] = str(form.get("inbound_method", "")).strip().lower() or None
    if "inbound_landing_zone" in form:
        updates["inbound_landing_zone"] = str(form.get("inbound_landing_zone", "")).strip() or None
    if "inbound_identifiers" in form:
        updates["inbound_identifiers"] = str(form.get("inbound_identifiers", "")).strip() or None
    if "inbound_reporting_layer" in form:
        updates["inbound_reporting_layer"] = str(form.get("inbound_reporting_layer", "")).strip() or None
    if "inbound_ingestion_notes" in form:
        updates["inbound_ingestion_notes"] = str(form.get("inbound_ingestion_notes", "")).strip() or None
    if "outbound_method" in form:
        updates["outbound_method"] = str(form.get("outbound_method", "")).strip().lower() or None
    if "outbound_creation_process" in form:
        updates["outbound_creation_process"] = str(form.get("outbound_creation_process", "")).strip() or None
    if "outbound_delivery_process" in form:
        updates["outbound_delivery_process"] = str(form.get("outbound_delivery_process", "")).strip() or None
    if "outbound_responsible_owner" in form:
        outbound_responsible_owner = str(form.get("outbound_responsible_owner", "")).strip()
        if outbound_responsible_owner:
            resolved_owner = repo.resolve_user_login_identifier(outbound_responsible_owner)
            if not resolved_owner:
                add_flash(request, "Outbound responsible owner must exist in the app user directory.", "error")
                return RedirectResponse(
                    url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
                    status_code=303,
                )
            outbound_responsible_owner = resolved_owner
        updates["outbound_responsible_owner"] = outbound_responsible_owner or None
    if "outbound_notes" in form:
        updates["outbound_notes"] = str(form.get("outbound_notes", "")).strip() or None

    if not updates:
        add_flash(request, "No profile fields were submitted.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    invalid_method_values = [
        value
        for value in [updates.get("inbound_method"), updates.get("outbound_method")]
        if value and value not in set(OFFERING_DATA_METHOD_OPTIONS)
    ]
    if invalid_method_values:
        add_flash(
            request,
            f"Data methods must be one of: {', '.join(OFFERING_DATA_METHOD_OPTIONS)}",
            "error",
        )
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    payload = {"offering_id": offering_id, "updates": updates, "reason": reason}
    try:
        if user.can_apply_change("update_offering_profile"):
            result = repo.save_offering_profile(
                vendor_id=vendor_id,
                offering_id=offering_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Offering profile updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_profile_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering profile: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/add")
async def add_offering_data_flow_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    reason = str(form.get("reason", "")).strip()
    direction = str(form.get("direction", "")).strip().lower()
    flow_name = str(form.get("flow_name", "")).strip()
    method = str(form.get("method", "")).strip().lower()
    data_description = str(form.get("data_description", "")).strip()
    endpoint_details = str(form.get("endpoint_details", "")).strip()
    identifiers = str(form.get("identifiers", "")).strip()
    reporting_layer = str(form.get("reporting_layer", "")).strip()
    creation_process = str(form.get("creation_process", "")).strip()
    delivery_process = str(form.get("delivery_process", "")).strip()
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    notes = str(form.get("notes", "")).strip()
    source_section = "dataflow"

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)
    if direction not in {"inbound", "outbound"}:
        add_flash(request, "Direction must be inbound or outbound.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not flow_name:
        add_flash(request, "Data flow name is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if method and method not in set(OFFERING_DATA_METHOD_OPTIONS):
        add_flash(request, f"Data method must be one of: {', '.join(OFFERING_DATA_METHOD_OPTIONS)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if owner_user_principal and not repo.resolve_user_login_identifier(owner_user_principal):
        add_flash(request, "Owner must exist in the app user directory.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "direction": direction,
        "flow_name": flow_name,
        "method": method or None,
        "data_description": data_description or None,
        "endpoint_details": endpoint_details or None,
        "identifiers": identifiers or None,
        "reporting_layer": reporting_layer or None,
        "creation_process": creation_process or None,
        "delivery_process": delivery_process or None,
        "owner_user_principal": owner_user_principal or None,
        "notes": notes or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("update_offering_profile"):
            data_flow_id = repo.add_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                direction=direction,
                flow_name=flow_name,
                method=method or None,
                data_description=data_description or None,
                endpoint_details=endpoint_details or None,
                identifiers=identifiers or None,
                reporting_layer=reporting_layer or None,
                creation_process=creation_process or None,
                delivery_process=delivery_process or None,
                owner_user_principal=owner_user_principal or None,
                notes=notes or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering data flow added: {data_flow_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload={"data_flow_action": "add", **payload},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_data_flow_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "direction": direction},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering data flow: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/remove")
async def remove_offering_data_flow_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    reason = str(form.get("reason", "")).strip()
    data_flow_id = str(form.get("data_flow_id", "")).strip()
    source_section = "dataflow"

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)
    if not data_flow_id:
        add_flash(request, "Data flow ID is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    try:
        if user.can_apply_change("update_offering_profile"):
            repo.remove_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                data_flow_id=data_flow_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering data flow removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload={
                    "offering_id": offering_id,
                    "data_flow_action": "remove",
                    "data_flow_id": data_flow_id,
                    "reason": reason,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_data_flow_remove",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "data_flow_id": data_flow_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering data flow: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/update")
async def update_offering_data_flow_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    reason = str(form.get("reason", "")).strip()
    data_flow_id = str(form.get("data_flow_id", "")).strip()
    direction = str(form.get("direction", "")).strip().lower()
    flow_name = str(form.get("flow_name", "")).strip()
    method = str(form.get("method", "")).strip().lower()
    data_description = str(form.get("data_description", "")).strip()
    endpoint_details = str(form.get("endpoint_details", "")).strip()
    identifiers = str(form.get("identifiers", "")).strip()
    reporting_layer = str(form.get("reporting_layer", "")).strip()
    creation_process = str(form.get("creation_process", "")).strip()
    delivery_process = str(form.get("delivery_process", "")).strip()
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    notes = str(form.get("notes", "")).strip()
    source_section = "dataflow"

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)
    if not data_flow_id:
        add_flash(request, "Data flow ID is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if direction not in {"inbound", "outbound"}:
        add_flash(request, "Direction must be inbound or outbound.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not flow_name:
        add_flash(request, "Data flow name is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if method and method not in set(OFFERING_DATA_METHOD_OPTIONS):
        add_flash(request, f"Data method must be one of: {', '.join(OFFERING_DATA_METHOD_OPTIONS)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if owner_user_principal and not repo.resolve_user_login_identifier(owner_user_principal):
        add_flash(request, "Owner must exist in the app user directory.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "data_flow_id": data_flow_id,
        "direction": direction,
        "flow_name": flow_name,
        "method": method or None,
        "data_description": data_description or None,
        "endpoint_details": endpoint_details or None,
        "identifiers": identifiers or None,
        "reporting_layer": reporting_layer or None,
        "creation_process": creation_process or None,
        "delivery_process": delivery_process or None,
        "owner_user_principal": owner_user_principal or None,
        "notes": notes or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("update_offering_profile"):
            result = repo.update_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                data_flow_id=data_flow_id,
                actor_user_principal=user.user_principal,
                updates={
                    "direction": direction,
                    "flow_name": flow_name,
                    "method": method or None,
                    "data_description": data_description or None,
                    "endpoint_details": endpoint_details or None,
                    "identifiers": identifiers or None,
                    "reporting_layer": reporting_layer or None,
                    "creation_process": creation_process or None,
                    "delivery_process": delivery_process or None,
                    "owner_user_principal": owner_user_principal or None,
                    "notes": notes or None,
                },
                reason=reason,
            )
            add_flash(
                request,
                f"Offering data flow updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload={"data_flow_action": "update", **payload},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_data_flow_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "data_flow_id": data_flow_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering data flow: {exc}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/notes/add")
async def add_offering_note_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    note_type = str(form.get("note_type", "general")).strip().lower() or "general"
    note_text = str(form.get("note_text", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if note_type not in set(OFFERING_NOTE_TYPES):
        add_flash(request, f"Note type must be one of: {', '.join(OFFERING_NOTE_TYPES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not note_text:
        add_flash(request, "Note text is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    try:
        if user.can_apply_change("add_offering_note"):
            note_id = repo.add_offering_note(
                vendor_id=vendor_id,
                offering_id=offering_id,
                note_type=note_type,
                note_text=note_text,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering note added: {note_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_note",
                payload={"offering_id": offering_id, "note_type": note_type, "note_text": note_text},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_note_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "note_type": note_type},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering note: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/tickets/add")
async def add_offering_ticket_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    title = str(form.get("title", "")).strip()
    ticket_system = str(form.get("ticket_system", "")).strip()
    external_ticket_id = str(form.get("external_ticket_id", "")).strip()
    status = str(form.get("status", "open")).strip().lower() or "open"
    priority = str(form.get("priority", "")).strip().lower()
    opened_date = str(form.get("opened_date", "")).strip()
    notes = str(form.get("notes", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if status not in set(OFFERING_TICKET_STATUSES):
        add_flash(request, f"Ticket status must be one of: {', '.join(OFFERING_TICKET_STATUSES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if priority and priority not in set(OFFERING_TICKET_PRIORITIES):
        add_flash(request, f"Ticket priority must be one of: {', '.join(OFFERING_TICKET_PRIORITIES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "title": title,
        "ticket_system": ticket_system or None,
        "external_ticket_id": external_ticket_id or None,
        "status": status,
        "priority": priority or None,
        "opened_date": opened_date or None,
        "notes": notes or None,
    }
    try:
        if user.can_apply_change("add_offering_ticket"):
            ticket_id = repo.add_offering_ticket(
                vendor_id=vendor_id,
                offering_id=offering_id,
                title=title,
                ticket_system=ticket_system or None,
                external_ticket_id=external_ticket_id or None,
                status=status,
                priority=priority or None,
                opened_date=opened_date or None,
                notes=notes or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering ticket added: {ticket_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_ticket",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_ticket_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "status": status},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering ticket: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/tickets/{ticket_id}/status")
async def update_offering_ticket_status_submit(request: Request, vendor_id: str, offering_id: str, ticket_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    status = str(form.get("status", "")).strip().lower()
    closed_date = str(form.get("closed_date", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if status not in set(OFFERING_TICKET_STATUSES):
        add_flash(request, f"Ticket status must be one of: {', '.join(OFFERING_TICKET_STATUSES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    payload = {
        "ticket_id": ticket_id,
        "offering_id": offering_id,
        "status": status,
        "closed_date": closed_date or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("update_offering_ticket"):
            result = repo.update_offering_ticket(
                vendor_id=vendor_id,
                offering_id=offering_id,
                ticket_id=ticket_id,
                actor_user_principal=user.user_principal,
                updates={
                    "status": status,
                    "closed_date": closed_date or None,
                },
                reason=reason,
            )
            add_flash(
                request,
                f"Offering ticket updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_ticket",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_ticket_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "ticket_id": ticket_id, "status": status},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering ticket: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/map-contract")
async def map_contract_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings")))
    contract_id = str(form.get("contract_id", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not contract_id:
        add_flash(request, "Contract ID is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    contracts_df = repo.get_vendor_contracts(vendor_id)
    if contracts_df[contracts_df["contract_id"].astype(str) == contract_id].empty:
        add_flash(request, "Contract does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if offering_id and not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Selected offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"contract_id": contract_id, "offering_id": offering_id or None, "reason": reason}
        if user.can_apply_change("map_contract_to_offering"):
            result = repo.map_contract_to_offering(
                contract_id=contract_id,
                vendor_id=vendor_id,
                offering_id=offering_id or None,
                actor_user_principal=user.user_principal,
                reason=reason,
            )
            add_flash(
                request,
                f"Contract mapping updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="map_contract_to_offering",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offerings",
            event_type="map_contract",
            payload={"vendor_id": vendor_id, "contract_id": contract_id, "offering_id": offering_id or None},
        )
    except Exception as exc:
        add_flash(request, f"Could not map contract: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/map-demo")
async def map_demo_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings")))
    demo_id = str(form.get("demo_id", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not demo_id:
        add_flash(request, "Demo ID is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    demos_df = repo.get_vendor_demos(vendor_id)
    if demos_df[demos_df["demo_id"].astype(str) == demo_id].empty:
        add_flash(request, "Demo does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if offering_id and not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Selected offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"demo_id": demo_id, "offering_id": offering_id or None, "reason": reason}
        if user.can_apply_change("map_demo_to_offering"):
            result = repo.map_demo_to_offering(
                demo_id=demo_id,
                vendor_id=vendor_id,
                offering_id=offering_id or None,
                actor_user_principal=user.user_principal,
                reason=reason,
            )
            add_flash(
                request,
                f"Demo mapping updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="map_demo_to_offering",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offerings",
            event_type="map_demo",
            payload={"vendor_id": vendor_id, "demo_id": demo_id, "offering_id": offering_id or None},
        )
    except Exception as exc:
        add_flash(request, f"Could not map demo: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/owners/add")
async def add_offering_owner_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "offering_id": offering_id,
            "owner_user_principal": owner_user_principal,
            "owner_role": owner_role,
            "reason": reason,
        }
        if user.can_apply_change("add_offering_owner"):
            owner_id = repo.add_offering_owner(
                vendor_id=vendor_id,
                offering_id=offering_id,
                owner_user_principal=owner_user_principal,
                owner_role=owner_role,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering owner added: {owner_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="add_offering_owner",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/owners/remove")
async def remove_offering_owner_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    offering_owner_id = str(form.get("offering_owner_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"offering_id": offering_id, "offering_owner_id": offering_owner_id, "reason": reason}
        if user.can_apply_change("remove_offering_owner"):
            repo.remove_offering_owner(
                vendor_id=vendor_id,
                offering_id=offering_id,
                offering_owner_id=offering_owner_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering owner removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_offering_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="remove_offering_owner",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/contacts/add")
async def add_offering_contact_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    full_name = str(form.get("full_name", "")).strip()
    contact_type = str(form.get("contact_type", "")).strip()
    email = str(form.get("email", "")).strip()
    phone = str(form.get("phone", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "offering_id": offering_id,
            "full_name": full_name,
            "contact_type": contact_type,
            "email": email,
            "phone": phone,
            "reason": reason,
        }
        if user.can_apply_change("add_offering_contact"):
            contact_id = repo.add_offering_contact(
                vendor_id=vendor_id,
                offering_id=offering_id,
                full_name=full_name,
                contact_type=contact_type,
                email=email or None,
                phone=phone or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering contact added: {contact_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_contact",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="add_offering_contact",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering contact: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/contacts/remove")
async def remove_offering_contact_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    offering_contact_id = str(form.get("offering_contact_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"offering_id": offering_id, "offering_contact_id": offering_contact_id, "reason": reason}
        if user.can_apply_change("remove_offering_contact"):
            repo.remove_offering_contact(
                vendor_id=vendor_id,
                offering_id=offering_id,
                offering_contact_id=offering_contact_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering contact removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_offering_contact",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="remove_offering_contact",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering contact: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.get("/{vendor_id}/projects")
def vendor_projects_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    projects = repo.list_projects(vendor_id).to_dict("records")
    for row in projects:
        project_id = str(row.get("project_id"))
        row["_open_link"] = (
            f"/projects/{project_id}/summary?return_to="
            f"{quote(f'/vendors/{vendor_id}/projects', safe='')}"
        )
        row["_edit_link"] = (
            f"/vendors/{vendor_id}/projects/{project_id}/edit?return_to={quote(base['return_to'], safe='')}"
        )

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Projects",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "summary": base["summary"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "projects": projects,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_projects.html", context)


@router.get("/{vendor_id}/projects/new")
def project_new_form(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to create projects.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    selected_vendor_rows = _selected_project_vendor_rows(repo, [vendor_id])
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - New Project",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "project_types": _project_type_options(repo),
            "project_statuses": PROJECT_STATUSES,
            "selected_vendor_rows": selected_vendor_rows,
            "selected_offering_rows": [],
            "form_action": f"/vendors/{vendor_id}/projects/new",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_new.html", context)


@router.post("/{vendor_id}/projects/new")
async def project_new_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create projects.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    linked_offerings = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()])
    linked_vendors = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()])
    if vendor_id not in linked_vendors:
        linked_vendors.insert(0, vendor_id)
    if linked_offerings:
        offering_rows = repo.get_offerings_by_ids(linked_offerings).to_dict("records")
        for row in offering_rows:
            offering_vendor_id = str(row.get("vendor_id") or "").strip()
            if offering_vendor_id and offering_vendor_id not in linked_vendors:
                linked_vendors.append(offering_vendor_id)
    linked_vendors = _dedupe_ordered(linked_vendors)
    try:
        project_payload = {
            "vendor_id": vendor_id,
            "vendor_ids": linked_vendors,
            "project_name": str(form.get("project_name", "")).strip(),
            "project_type": _normalize_project_type(repo, str(form.get("project_type", "other"))),
            "status": _normalize_project_status(str(form.get("status", "draft"))),
            "start_date": str(form.get("start_date", "")).strip() or None,
            "target_date": str(form.get("target_date", "")).strip() or None,
            "owner_principal": str(form.get("owner_principal", "")).strip() or None,
            "description": str(form.get("description", "")).strip() or None,
            "linked_offering_ids": linked_offerings,
        }
        if user.can_apply_change("create_project"):
            project_id = repo.create_project(
                vendor_id=vendor_id,
                vendor_ids=linked_vendors,
                actor_user_principal=user.user_principal,
                project_name=project_payload["project_name"],
                project_type=project_payload["project_type"],
                status=project_payload["status"],
                start_date=project_payload["start_date"],
                target_date=project_payload["target_date"],
                owner_principal=project_payload["owner_principal"],
                description=project_payload["description"],
                linked_offering_ids=linked_offerings,
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_projects",
                event_type="project_create",
                payload={"vendor_id": vendor_id, "project_id": project_id},
            )
            add_flash(request, f"Project created: {project_id}", "success")
            return RedirectResponse(
                url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
                status_code=303,
            )
        request_id = repo.create_vendor_change_request(
            vendor_id=_request_scope_vendor_id(vendor_id),
            requestor_user_principal=user.user_principal,
            change_type="create_project",
            payload=project_payload,
        )
        add_flash(request, f"Pending change request submitted: {request_id}", "success")
        return RedirectResponse(url="/workflows?status=pending", status_code=303)
    except Exception as exc:
        add_flash(request, f"Could not create project: {exc}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects/new?return_to={quote(return_to, safe='')}",
            status_code=303,
        )


@router.get("/{vendor_id}/projects/{project_id}")
def project_detail_page(request: Request, vendor_id: str, project_id: str, return_to: str = "/vendors"):
    return RedirectResponse(
        url=f"/projects/{project_id}/summary?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )


@router.get("/{vendor_id}/projects/{project_id}/edit")
def project_edit_form(request: Request, vendor_id: str, project_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    project = repo.get_project(vendor_id, project_id)
    if project is None:
        add_flash(request, "Project not found for vendor.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to edit projects.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    project_vendor_ids = _dedupe_ordered([str(x).strip() for x in (project.get("vendor_ids") or []) if str(x).strip()])
    project_offering_ids = _dedupe_ordered(
        [str(x).strip() for x in (project.get("linked_offering_ids") or []) if str(x).strip()]
    )
    if vendor_id and vendor_id not in project_vendor_ids:
        project_vendor_ids.insert(0, vendor_id)
    selected_vendor_rows = _selected_project_vendor_rows(repo, project_vendor_ids)
    selected_offering_rows = _selected_project_offering_rows(repo, project_offering_ids)
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Edit Project",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "project": project,
            "selected_vendor_rows": selected_vendor_rows,
            "selected_offering_rows": selected_offering_rows,
            "return_to": base["return_to"],
            "project_types": _project_type_options(repo),
            "project_statuses": PROJECT_STATUSES,
            "form_action": f"/vendors/{vendor_id}/projects/{project_id}/edit",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_edit.html", context)


@router.post("/{vendor_id}/projects/{project_id}/edit")
async def project_edit_submit(request: Request, vendor_id: str, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have permission to edit projects.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    linked_offerings = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()])
    linked_vendors = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()])
    if vendor_id not in linked_vendors:
        linked_vendors.insert(0, vendor_id)
    if linked_offerings:
        offering_rows = repo.get_offerings_by_ids(linked_offerings).to_dict("records")
        for row in offering_rows:
            offering_vendor_id = str(row.get("vendor_id") or "").strip()
            if offering_vendor_id and offering_vendor_id not in linked_vendors:
                linked_vendors.append(offering_vendor_id)
    linked_vendors = _dedupe_ordered(linked_vendors)
    updates = {
        "project_name": str(form.get("project_name", "")).strip(),
        "project_type": str(form.get("project_type", "other")),
        "status": str(form.get("status", "draft")),
        "start_date": str(form.get("start_date", "")).strip() or None,
        "target_date": str(form.get("target_date", "")).strip() or None,
        "owner_principal": str(form.get("owner_principal", "")).strip() or None,
        "description": str(form.get("description", "")).strip() or None,
    }

    try:
        updates["project_type"] = _normalize_project_type(repo, str(updates.get("project_type", "other")))
        updates["status"] = _normalize_project_status(str(updates.get("status", "draft")))
        if user.can_apply_change("update_project"):
            result = repo.update_project(
                vendor_id=vendor_id,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                vendor_ids=linked_vendors,
                linked_offering_ids=linked_offerings,
                reason=reason,
            )
            add_flash(
                request,
                f"Project updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_project",
                payload={"project_id": project_id, "updates": updates, "linked_offering_ids": linked_offerings, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_project_detail",
            event_type="project_update",
            payload={"vendor_id": vendor_id, "project_id": project_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update project: {exc}", "error")

    return RedirectResponse(
        url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.get("/{vendor_id}/projects/{project_id}/demos/new")
def project_demo_new_form(request: Request, vendor_id: str, project_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    project = repo.get_project(vendor_id, project_id)
    if project is None:
        add_flash(request, "Project not found for vendor.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/demos?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to add demos.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/demos?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    offerings = repo.get_vendor_offerings(vendor_id).to_dict("records")
    vendor_demos = repo.get_vendor_demos(vendor_id).to_dict("records")
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - New Project Demo",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "project": project,
            "return_to": base["return_to"],
            "offerings": offerings,
            "project_demo_types": PROJECT_DEMO_TYPES,
            "project_demo_outcomes": PROJECT_DEMO_OUTCOMES,
            "demo_map_options": _project_demo_select_options(vendor_demos),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_demo_new.html", context)


@router.post("/{vendor_id}/projects/{project_id}/demos/new")
async def project_demo_new_submit(request: Request, vendor_id: str, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    linked_vendor_demo_id = str(form.get("linked_vendor_demo_id", "")).strip()
    try:
        demo_payload = {
            "vendor_id": vendor_id,
            "project_id": project_id,
            "demo_name": str(form.get("demo_name", "")).strip(),
            "demo_datetime_start": str(form.get("demo_datetime_start", "")).strip() or None,
            "demo_datetime_end": str(form.get("demo_datetime_end", "")).strip() or None,
            "demo_type": str(form.get("demo_type", "live")).strip() or "live",
            "outcome": str(form.get("outcome", "unknown")).strip() or "unknown",
            "score": float(str(form.get("score", "")).strip()) if str(form.get("score", "")).strip() else None,
            "attendees_internal": str(form.get("attendees_internal", "")).strip() or None,
            "attendees_vendor": str(form.get("attendees_vendor", "")).strip() or None,
            "notes": str(form.get("notes", "")).strip() or None,
            "followups": str(form.get("followups", "")).strip() or None,
            "linked_offering_id": str(form.get("linked_offering_id", "")).strip() or None,
            "linked_vendor_demo_id": linked_vendor_demo_id or None,
        }
        if user.can_apply_change("create_project_demo"):
            demo_id = repo.create_project_demo(
                vendor_id=vendor_id,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                demo_name=demo_payload["demo_name"],
                demo_datetime_start=demo_payload["demo_datetime_start"],
                demo_datetime_end=demo_payload["demo_datetime_end"],
                demo_type=demo_payload["demo_type"],
                outcome=demo_payload["outcome"],
                score=demo_payload["score"],
                attendees_internal=demo_payload["attendees_internal"],
                attendees_vendor=demo_payload["attendees_vendor"],
                notes=demo_payload["notes"],
                followups=demo_payload["followups"],
                linked_offering_id=demo_payload["linked_offering_id"],
                linked_vendor_demo_id=demo_payload["linked_vendor_demo_id"],
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_project_detail",
                event_type="project_demo_create",
                payload={"vendor_id": vendor_id, "project_id": project_id, "project_demo_id": demo_id},
            )
            add_flash(request, f"Project demo created: {demo_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(vendor_id),
                requestor_user_principal=user.user_principal,
                change_type="create_project_demo",
                payload=demo_payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not create project demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/map")
async def project_demo_map_submit(request: Request, vendor_id: str, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    vendor_demo_id = str(form.get("vendor_demo_id", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to map demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not vendor_demo_id:
        add_flash(request, "Vendor demo is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        demo_id = repo.map_vendor_demo_to_project(
            vendor_id=vendor_id,
            project_id=project_id,
            vendor_demo_id=vendor_demo_id,
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_project_detail",
            event_type="project_demo_map",
            payload={"vendor_id": vendor_id, "project_id": project_id, "vendor_demo_id": vendor_demo_id, "project_demo_id": demo_id},
        )
        add_flash(request, f"Vendor demo mapped to project: {demo_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not map vendor demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/update")
async def project_demo_update_submit(request: Request, vendor_id: str, project_id: str, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to update demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    updates = {
        "demo_name": str(form.get("demo_name", "")).strip(),
        "demo_datetime_start": str(form.get("demo_datetime_start", "")).strip() or None,
        "demo_datetime_end": str(form.get("demo_datetime_end", "")).strip() or None,
        "demo_type": str(form.get("demo_type", "")).strip() or None,
        "outcome": str(form.get("outcome", "")).strip() or None,
        "score": float(str(form.get("score", "")).strip()) if str(form.get("score", "")).strip() else None,
        "attendees_internal": str(form.get("attendees_internal", "")).strip() or None,
        "attendees_vendor": str(form.get("attendees_vendor", "")).strip() or None,
        "notes": str(form.get("notes", "")).strip() or None,
        "followups": str(form.get("followups", "")).strip() or None,
        "linked_offering_id": str(form.get("linked_offering_id", "")).strip() or None,
    }
    updates = {k: v for k, v in updates.items() if v is not None and v != ""}

    try:
        if user.can_apply_change("update_project_demo"):
            result = repo.update_project_demo(
                vendor_id=vendor_id,
                project_id=project_id,
                project_demo_id=demo_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Project demo updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_project_demo",
                payload={"project_id": project_id, "project_demo_id": demo_id, "updates": updates, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_project_detail",
            event_type="project_demo_update",
            payload={"vendor_id": vendor_id, "project_id": project_id, "project_demo_id": demo_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update project demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/remove")
async def project_demo_remove_submit(request: Request, vendor_id: str, project_id: str, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to remove demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_apply_change("remove_project_demo"):
            repo.remove_project_demo(
                vendor_id=vendor_id,
                project_id=project_id,
                project_demo_id=demo_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Project demo removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_project_demo",
                payload={"project_id": project_id, "project_demo_id": demo_id},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not remove project demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


def _entity_exists_for_doc(repo, vendor_id: str, entity_type: str, entity_id: str) -> bool:
    if entity_type == "vendor":
        return not repo.get_vendor_profile(vendor_id).empty and str(entity_id) == str(vendor_id)
    if entity_type == "project":
        return repo.project_belongs_to_vendor(vendor_id, entity_id)
    if entity_type == "offering":
        return repo.offering_belongs_to_vendor(vendor_id, entity_id)
    if entity_type == "demo":
        project_rows = repo.list_projects(vendor_id).to_dict("records")
        for row in project_rows:
            demos = repo.list_project_demos(vendor_id, str(row.get("project_id")))
            if not demos.empty and not demos[demos["project_demo_id"].astype(str) == str(entity_id)].empty:
                return True
        return False
    return False


async def _create_doc_link_for_entity(
    request: Request,
    *,
    form,
    vendor_id: str,
    entity_type: str,
    entity_id: str,
    page_name: str,
    event_payload: dict[str, str],
    redirect_url: str,
):
    repo = get_repo()
    user = get_user_context(request)
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to or redirect_url, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add document links.", "error")
        return RedirectResponse(url=return_to or redirect_url, status_code=303)
    if not _entity_exists_for_doc(repo, vendor_id, entity_type, entity_id):
        add_flash(request, "Target record was not found for this vendor.", "error")
        return RedirectResponse(url=return_to or redirect_url, status_code=303)

    try:
        payload = _prepare_doc_payload(
            repo,
            {
                "doc_url": str(form.get("doc_url", "")),
                "doc_type": str(form.get("doc_type", "")),
                "doc_title": str(form.get("doc_title", "")),
                "tags": [str(v) for v in form.getlist("tags") if str(v).strip()],
                "owner": str(form.get("owner", "")),
            },
            actor_user_principal=user.user_principal,
        )
        if user.can_apply_change("create_doc_link"):
            doc_id = repo.create_doc_link(
                entity_type=entity_type,
                entity_id=entity_id,
                doc_title=payload["doc_title"],
                doc_url=payload["doc_url"],
                doc_type=payload["doc_type"],
                tags=payload["tags"] or None,
                doc_fqdn=payload["doc_fqdn"] or None,
                owner=payload["owner"] or None,
                actor_user_principal=user.user_principal,
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name=page_name,
                event_type="doc_link_create",
                payload={**event_payload, "doc_id": doc_id, "entity_type": entity_type},
            )
            add_flash(request, f"Document link added: {payload['doc_title']}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(vendor_id),
                requestor_user_principal=user.user_principal,
                change_type="create_doc_link",
                payload={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "doc_title": payload["doc_title"],
                    "doc_url": payload["doc_url"],
                    "doc_type": payload["doc_type"],
                    "tags": payload["tags"] or None,
                    "doc_fqdn": payload["doc_fqdn"] or None,
                    "owner": payload["owner"] or None,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not add document link: {exc}", "error")
    target = return_to or redirect_url
    return RedirectResponse(url=target, status_code=303)


@router.post("/{vendor_id}/docs/link")
async def vendor_doc_link_submit(request: Request, vendor_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/summary")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="vendor",
        entity_id=vendor_id,
        page_name="vendor_summary",
        event_payload={"vendor_id": vendor_id},
        redirect_url=f"/vendors/{vendor_id}/summary?return_to={quote(return_to, safe='')}",
    )


@router.post("/{vendor_id}/projects/{project_id}/docs/link")
async def project_doc_link_submit(request: Request, vendor_id: str, project_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/docs")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="project",
        entity_id=project_id,
        page_name="vendor_project_detail",
        event_payload={"vendor_id": vendor_id, "project_id": project_id},
        redirect_url=f"/vendors/{vendor_id}/projects/{project_id}?return_to={quote(return_to, safe='')}",
    )


@router.post("/{vendor_id}/offerings/{offering_id}/docs/link")
async def offering_doc_link_submit(request: Request, vendor_id: str, offering_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="offering",
        entity_id=offering_id,
        page_name="vendor_offering_detail",
        event_payload={"vendor_id": vendor_id, "offering_id": offering_id},
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?return_to={quote(return_to, safe='')}",
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/docs/link")
async def project_demo_doc_link_submit(request: Request, vendor_id: str, project_id: str, demo_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/demos")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="demo",
        entity_id=demo_id,
        page_name="vendor_project_detail",
        event_payload={"vendor_id": vendor_id, "project_id": project_id, "project_demo_id": demo_id},
        redirect_url=f"/vendors/{vendor_id}/projects/{project_id}?return_to={quote(return_to, safe='')}",
    )


@router.post("/docs/{doc_id}/remove")
async def doc_link_remove_submit(request: Request, doc_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to remove document links.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    doc = repo.get_doc_link(doc_id)
    if not doc:
        add_flash(request, "Document link not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    try:
        if user.can_apply_change("remove_doc_link"):
            repo.remove_doc_link(doc_id=doc_id, actor_user_principal=user.user_principal)
            add_flash(request, "Document link removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(str(form.get("vendor_id", "")).strip() or str(doc.get("entity_id"))),
                requestor_user_principal=user.user_principal,
                change_type="remove_doc_link",
                payload={"doc_id": doc_id},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_docs",
            event_type="doc_link_remove",
            payload={"doc_id": doc_id, "entity_type": str(doc.get("entity_type"))},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove document link: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)

@router.get("/{vendor_id}/contracts")
def vendor_contracts_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "contracts", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Contracts",
        active_nav="vendors",
        extra={
            "section": "contracts",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "contracts": repo.get_vendor_contracts(vendor_id).to_dict("records"),
            "contract_events": repo.get_vendor_contract_events(vendor_id).to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/demos")
def vendor_demos_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "demos", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Demos",
        active_nav="vendors",
        extra={
            "section": "demos",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "demos": repo.get_vendor_demos(vendor_id).to_dict("records"),
            "demo_scores": repo.get_vendor_demo_scores(vendor_id).to_dict("records"),
            "demo_notes": repo.get_vendor_demo_notes(vendor_id).to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/lineage")
def vendor_lineage_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "lineage", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Lineage/Audit",
        active_nav="vendors",
        extra={
            "section": "lineage",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "source_lineage": repo.get_vendor_source_lineage(vendor_id).to_dict("records"),
            "change_requests": repo.get_vendor_change_requests(vendor_id).to_dict("records"),
            "audit_events": repo.get_vendor_audit_events(vendor_id).to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/changes")
def vendor_changes_page(request: Request, vendor_id: str, return_to: str = "/vendors"):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "changes", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Changes",
        active_nav="vendors",
        extra={
            "section": "changes",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "profile": base["profile"].to_dict("records"),
            "recent_audit": repo.get_vendor_audit_events(vendor_id).head(5).to_dict("records"),
            "lifecycle_states": LIFECYCLE_STATES,
            "risk_tiers": RISK_TIERS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/direct-update")
async def vendor_direct_update(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)
    if not user.can_apply_change("update_vendor_profile"):
        required_level = required_approval_level("update_vendor_profile")
        add_flash(request, f"Direct updates require approval level {required_level} or higher.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

    profile = repo.get_vendor_profile(vendor_id)
    if profile.empty:
        add_flash(request, f"Vendor {vendor_id} not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    current = profile.iloc[0].to_dict()
    candidate_updates = {
        "legal_name": str(form.get("legal_name", "")).strip(),
        "display_name": str(form.get("display_name", "")).strip(),
        "lifecycle_state": str(form.get("lifecycle_state", "")).strip(),
        "owner_org_id": str(form.get("owner_org_id", "")).strip(),
        "risk_tier": str(form.get("risk_tier", "")).strip(),
    }
    updates = {key: value for key, value in candidate_updates.items() if value != str(current.get(key, "")).strip()}
    reason = str(form.get("reason", "")).strip()

    if not updates:
        add_flash(request, "No field values changed.", "info")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)
    if not reason:
        add_flash(request, "Reason for change is required.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

    try:
        result = repo.apply_vendor_profile_update(
            vendor_id=vendor_id,
            actor_user_principal=user.user_principal,
            updates=updates,
            reason=reason,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_360",
            event_type="apply_vendor_update",
            payload={"vendor_id": vendor_id, "fields": sorted(list(updates.keys()))},
        )
        add_flash(
            request,
            f"Vendor updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
            "success",
        )
    except Exception as exc:
        add_flash(request, f"Could not apply update: {exc}", "error")

    return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)


@router.post("/{vendor_id}/change-request")
async def vendor_change_request(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/vendors")))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)
    if not user.can_submit_requests:
        add_flash(request, "You do not have permission to submit change requests.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

    change_type = str(form.get("change_type", "update_vendor_profile"))
    change_notes = str(form.get("change_notes", "")).strip()
    requested_level_raw = str(form.get("approval_level_required", "")).strip()
    assigned_approver = str(form.get("assigned_approver", "")).strip()
    try:
        minimum_level = required_approval_level(change_type)
        requested_level = minimum_level
        if requested_level_raw:
            requested_level = max(MIN_CHANGE_APPROVAL_LEVEL, min(int(requested_level_raw), MAX_APPROVAL_LEVEL))
            requested_level = max(requested_level, minimum_level)
        payload = {"notes": change_notes}
        payload_meta: dict[str, object] = {}
        if requested_level != minimum_level:
            payload_meta["approval_level_required"] = requested_level
        if assigned_approver:
            payload_meta["assigned_approver"] = assigned_approver
        if payload_meta:
            payload["_meta"] = payload_meta
        request_id = repo.create_vendor_change_request(
            vendor_id=vendor_id,
            requestor_user_principal=user.user_principal,
            change_type=change_type,
            payload=payload,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_360",
            event_type="submit_change_request",
            payload={
                "vendor_id": vendor_id,
                "change_type": change_type,
                "approval_level_required": requested_level,
                "assigned_approver": assigned_approver or None,
            },
        )
        add_flash(request, f"Change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not submit change request: {exc}", "error")
    return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

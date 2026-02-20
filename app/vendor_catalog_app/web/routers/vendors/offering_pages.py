from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _offering_nav,
    _offering_select_options,
    _request_scope_vendor_id,
    _safe_return_to,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    CONTACT_ADD_REASON_OPTIONS,
    CONTACT_REMOVE_REASON_OPTIONS,
    CONTRACT_CHANGE_REASON_OPTIONS,
    CONTRACT_CANCEL_REASON_OPTIONS,
    CONTRACT_MAPPING_REASON_OPTIONS,
    CONTRACT_STATUS_OPTIONS,
    DEMO_MAPPING_REASON_OPTIONS,
    LIFECYCLE_STATES,
    OFFERING_DATAFLOW_CHANGE_REASON_OPTIONS,
    OFFERING_DATAFLOW_REMOVE_REASON_OPTIONS,
    OFFERING_DATA_METHOD_OPTIONS,
    OFFERING_INVOICE_ADD_REASON_OPTIONS,
    OFFERING_INVOICE_REMOVE_REASON_OPTIONS,
    OFFERING_INVOICE_STATUSES,
    OFFERING_NOTE_TYPES,
    OFFERING_PROFILE_REASON_OPTIONS,
    OFFERING_SECTIONS,
    OFFERING_TICKET_UPDATE_REASON_OPTIONS,
    OFFERING_TICKET_PRIORITIES,
    OFFERING_TICKET_STATUSES,
    OFFERING_UPDATE_REASON_OPTIONS,
    VENDOR_DEFAULT_RETURN_TO,
    OWNER_ADD_REASON_OPTIONS,
    OWNER_REMOVE_REASON_OPTIONS,
    OWNER_ROLE_UPDATE_REASON_OPTIONS,
    OWNER_REASSIGN_REASON_OPTIONS,
    ORG_ASSIGNMENT_REASON_OPTIONS,
)
from vendor_catalog_app.web.routers.vendors.pages import (
    _normalize_lifecycle,
    _normalize_offering_lob,
    _normalize_offering_service_type,
    _normalize_offering_type,
    _offering_invoice_summary,
    _offering_lob_options,
    _offering_service_type_options,
    _offering_type_options,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")

@router.get("/{vendor_id}/offerings")
def vendor_offerings_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "offerings", return_to)
    if isinstance(base, RedirectResponse):
        return base
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
    bulk_offering_options = [row for row in offering_options if str(row.get("offering_id") or "").strip()]
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
            "bulk_offering_options": bulk_offering_options,
            "unassigned_contracts": unassigned_contracts,
            "unassigned_demos": unassigned_demos,
            "offerings_return_to": offerings_return_to,
            "doc_source_options": repo.list_doc_source_options(),
            "contract_mapping_reason_options": CONTRACT_MAPPING_REASON_OPTIONS,
            "demo_mapping_reason_options": DEMO_MAPPING_REASON_OPTIONS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_offerings.html", context)


@router.get("/{vendor_id}/offerings/new")
def offering_new_form(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "offerings", return_to)
    if isinstance(base, RedirectResponse):
        return base
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
@require_permission("offering_create")
async def offering_new_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
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
    return_to: str = VENDOR_DEFAULT_RETURN_TO,
    section: str = "summary",
    edit: int = 0,
    edit_data_flow_id: str = "",
    new_data_feed: int = 0,
):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "offerings", return_to)
    if isinstance(base, RedirectResponse):
        return base
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
        offering_invoices = repo.list_offering_invoices(vendor_id, offering_id).to_dict("records")
        offering_notes = repo.list_offering_notes(offering_id).to_dict("records")
        offering_activity = repo.get_offering_activity(vendor_id, offering_id).head(50).to_dict("records")
    except Exception as exc:
        add_flash(
            request,
            (
                "Offering operations tables are not available. Run setup/v1_schema/databricks SQL scripts (00->90) "
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
        offering_invoices = []
        offering_notes = []
        offering_activity = []
    inbound_data_flows = [
        row for row in offering_data_flows if str(row.get("direction", "")).strip().lower() == "inbound"
    ]
    outbound_data_flows = [
        row for row in offering_data_flows if str(row.get("direction", "")).strip().lower() == "outbound"
    ]
    offering_invoice_summary = _offering_invoice_summary(offering_profile, offering_invoices, window_months=3)
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

    owner_subset = owners_df[owners_df["offering_id"].astype(str) == str(offering_id)].copy()
    if "active_flag" in owner_subset.columns:
        active_mask = ~owner_subset["active_flag"].astype(str).str.strip().str.lower().isin({"0", "false", "no", "n"})
        owner_subset = owner_subset[active_mask]
    offering_owner_rows = owner_subset.to_dict("records")
    owner_principals = [str(row.get("owner_user_principal") or "").strip() for row in offering_owner_rows]
    owner_status_map = repo.get_employee_directory_status_map(owner_principals)
    owner_assignment_count_map: dict[str, int] = {}
    unique_principals = sorted({principal for principal in owner_principals if principal})
    for principal in unique_principals:
        normalized_principal = principal.lower()
        try:
            owner_rows = repo.report_owner_coverage(owner_principal=principal, limit=5000)
            if owner_rows.empty:
                owner_assignment_count_map[normalized_principal] = 0
                continue
            exact_rows = owner_rows[
                owner_rows["owner_principal"].astype(str).str.strip().str.lower() == normalized_principal
            ]
            owner_assignment_count_map[normalized_principal] = int(len(exact_rows))
        except Exception:
            owner_assignment_count_map[normalized_principal] = 0
    owner_integrity_warning_count = 0
    for row in offering_owner_rows:
        principal = str(row.get("owner_user_principal") or "").strip()
        normalized = principal.lower()
        total_assignments = owner_assignment_count_map.get(normalized, 0)
        if principal and total_assignments <= 0:
            total_assignments = 1
        status_row = owner_status_map.get(
            normalized,
            {
                "status": "missing",
                "active": False,
                "login_identifier": None,
                "display_name": None,
            },
        )
        owner_status = str(status_row.get("status") or "missing").strip().lower()
        active_assignment = str(row.get("active_flag") or "").strip().lower() not in {"0", "false", "no", "n"}
        row["owner_identity_status"] = owner_status
        row["owner_identity_active"] = bool(status_row.get("active"))
        row["owner_identity_display_name"] = str(status_row.get("display_name") or "").strip()
        row["owner_identity_warning"] = bool(active_assignment and owner_status != "active")
        row["owner_assignment_count"] = int(total_assignments)
        row["owner_other_assignment_count"] = max(0, int(total_assignments) - 1)
        if row["owner_identity_warning"]:
            owner_integrity_warning_count += 1

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
            "offering_owners": offering_owner_rows,
            "owner_integrity_warning_count": owner_integrity_warning_count,
            "offering_contacts": contacts_df[contacts_df["offering_id"].astype(str) == str(offering_id)].to_dict("records"),
            "offering_contracts": current_contracts,
            "offering_demos": current_demos,
            "offering_docs": offering_docs,
            "offering_profile": offering_profile,
            "offering_data_flows": offering_data_flows,
            "inbound_data_flows": inbound_data_flows,
            "outbound_data_flows": outbound_data_flows,
            "offering_tickets": offering_tickets,
            "offering_invoices": offering_invoices,
            "offering_invoice_summary": offering_invoice_summary,
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
            "offering_invoice_statuses": OFFERING_INVOICE_STATUSES,
            "contract_status_options": CONTRACT_STATUS_OPTIONS,
            "contract_cancel_reason_options": CONTRACT_CANCEL_REASON_OPTIONS,
            "contract_change_reason_options": CONTRACT_CHANGE_REASON_OPTIONS,
            "contract_mapping_reason_options": CONTRACT_MAPPING_REASON_OPTIONS,
            "demo_mapping_reason_options": DEMO_MAPPING_REASON_OPTIONS,
            "owner_remove_reason_options": OWNER_REMOVE_REASON_OPTIONS,
            "owner_reassign_reason_options": OWNER_REASSIGN_REASON_OPTIONS,
            "owner_add_reason_options": OWNER_ADD_REASON_OPTIONS,
            "owner_role_update_reason_options": OWNER_ROLE_UPDATE_REASON_OPTIONS,
            "org_assignment_reason_options": ORG_ASSIGNMENT_REASON_OPTIONS,
            "contact_add_reason_options": CONTACT_ADD_REASON_OPTIONS,
            "contact_remove_reason_options": CONTACT_REMOVE_REASON_OPTIONS,
            "offering_update_reason_options": OFFERING_UPDATE_REASON_OPTIONS,
            "offering_profile_reason_options": OFFERING_PROFILE_REASON_OPTIONS,
            "offering_dataflow_change_reason_options": OFFERING_DATAFLOW_CHANGE_REASON_OPTIONS,
            "offering_dataflow_remove_reason_options": OFFERING_DATAFLOW_REMOVE_REASON_OPTIONS,
            "offering_invoice_add_reason_options": OFFERING_INVOICE_ADD_REASON_OPTIONS,
            "offering_invoice_remove_reason_options": OFFERING_INVOICE_REMOVE_REASON_OPTIONS,
            "offering_ticket_update_reason_options": OFFERING_TICKET_UPDATE_REASON_OPTIONS,
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
@require_permission("offering_edit")
async def offering_update_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
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


@router.post("/{vendor_id}/offerings/{offering_id}/ownership/lob/update")
@require_permission("offering_edit")
async def offering_ownership_lob_update_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(
        str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}?section=ownership"))
    )
    selected_lobs = [str(item).strip() for item in form.getlist("lobs") if str(item).strip()]
    submitted_multi_lobs = bool(selected_lobs)
    legacy_lob = str(form.get("lob", "")).strip()
    if legacy_lob and legacy_lob not in selected_lobs:
        selected_lobs.insert(0, legacy_lob)
    primary_lob = str(form.get("primary_lob", "")).strip()
    if not primary_lob and legacy_lob and not submitted_multi_lobs:
        primary_lob = legacy_lob
    reason_code = str(form.get("reason_code", "")).strip().lower() or "ownership_alignment"
    if reason_code not in set(ORG_ASSIGNMENT_REASON_OPTIONS):
        reason_code = "ownership_alignment"
    reason_other_detail = str(form.get("reason_other_detail", "")).strip()
    if reason_code == "other":
        if not reason_other_detail:
            add_flash(request, "Enter a reason when 'Other' is selected.", "error")
            return RedirectResponse(url=return_to, status_code=303)
        reason = f"other: {reason_other_detail}"
    else:
        reason = reason_code

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    current_offering = repo.get_offering_record(vendor_id, offering_id)
    if current_offering is None:
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)

    try:
        existing_lob = str(current_offering.get("lob") or "").strip()
        allowed_lobs = _offering_lob_options(repo)
        canonical_by_lower = {str(item).lower(): str(item) for item in allowed_lobs}
        normalized_lobs: list[str] = []
        for candidate in selected_lobs:
            canonical = canonical_by_lower.get(candidate.lower())
            if canonical and canonical not in normalized_lobs:
                normalized_lobs.append(canonical)
        if not normalized_lobs:
            raise ValueError("Line of Business must be selected from the admin-managed list.")
        normalized_lob = _normalize_offering_lob(
            repo,
            primary_lob,
            allow_blank=True,
            extra_allowed={existing_lob} if existing_lob else None,
        )
        if normalized_lob and normalized_lob not in normalized_lobs:
            raise ValueError("Primary line of business must be one of the selected lines of business.")

        payload_updates = {"lob": normalized_lob}
        if user.can_apply_change("update_offering"):
            result = repo.update_offering_fields(
                vendor_id=vendor_id,
                offering_id=offering_id,
                actor_user_principal=user.user_principal,
                updates=payload_updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Line of Business updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering",
                payload={"offering_id": offering_id, "updates": payload_updates, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")

        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_ownership_lob_update",
            payload={
                "vendor_id": vendor_id,
                "offering_id": offering_id,
                "lob": normalized_lob,
                "lobs": normalized_lobs,
                "reason_code": reason_code,
                "reason_other_detail": reason_other_detail,
            },
        )
    except Exception as exc:
        add_flash(request, f"Could not update Line of Business: {exc}", "error")

    return RedirectResponse(url=return_to, status_code=303)






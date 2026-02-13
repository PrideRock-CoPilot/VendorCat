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
    CONTRACT_CANCEL_REASON_OPTIONS,
    CONTRACT_STATUS_OPTIONS,
    LIFECYCLE_STATES,
    OFFERING_DATA_METHOD_OPTIONS,
    OFFERING_INVOICE_STATUSES,
    OFFERING_NOTE_TYPES,
    OFFERING_SECTIONS,
    OFFERING_TICKET_PRIORITIES,
    OFFERING_TICKET_STATUSES,
    VENDOR_DEFAULT_RETURN_TO,
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

router = APIRouter(prefix="/vendors")

@router.get("/{vendor_id}/offerings")
def vendor_offerings_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
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
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_offerings.html", context)


@router.get("/{vendor_id}/offerings/new")
def offering_new_form(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
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






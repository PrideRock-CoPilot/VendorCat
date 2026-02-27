from __future__ import annotations

from django.urls import path

from apps.offerings import views

urlpatterns = [
    path("", views.index, name="offerings-home"),
    path("new", views.offering_form_page, name="offerings-create"),
    path("<str:offering_id>", views.offering_detail_page, name="offerings-detail"),
    path("<str:offering_id>/edit", views.offering_form_page, name="offerings-edit"),
    path(
        "<str:offering_id>/program-profile/update",
        views.offering_program_profile_form_submit,
        name="offerings-program-profile-update",
    ),
    path(
        "<str:offering_id>/entitlements/new",
        views.offering_entitlement_form_submit,
        name="offerings-entitlement-create",
    ),
    path(
        "<str:offering_id>/entitlements/<int:entitlement_id>/delete",
        views.offering_entitlement_delete_form_submit,
        name="offerings-entitlement-delete",
    ),
    path(
        "<str:offering_id>/contacts/new",
        views.offering_contact_form_submit,
        name="offerings-contact-create",
    ),
    path(
        "<str:offering_id>/contacts/<int:contact_id>/edit",
        views.offering_contact_edit_form_submit,
        name="offerings-contact-edit",
    ),
    path(
        "<str:offering_id>/contacts/<int:contact_id>/delete",
        views.offering_contact_delete_form_submit,
        name="offerings-contact-delete",
    ),
    path(
        "<str:offering_id>/contracts/new",
        views.offering_contract_form_submit,
        name="offerings-contract-create",
    ),
    path(
        "<str:offering_id>/data-flows/new",
        views.offering_data_flow_form_submit,
        name="offerings-data-flow-create",
    ),
    path(
        "<str:offering_id>/data-flows/<int:flow_id>/edit",
        views.offering_data_flow_edit_form_submit,
        name="offerings-data-flow-edit",
    ),
    path(
        "<str:offering_id>/data-flows/<int:flow_id>/delete",
        views.offering_data_flow_delete_form_submit,
        name="offerings-data-flow-delete",
    ),
    path(
        "<str:offering_id>/service-tickets/new",
        views.offering_service_ticket_form_submit,
        name="offerings-service-ticket-create",
    ),
    path(
        "<str:offering_id>/service-tickets/<int:ticket_id>/edit",
        views.offering_service_ticket_edit_form_submit,
        name="offerings-service-ticket-edit",
    ),
    path(
        "<str:offering_id>/service-tickets/<int:ticket_id>/delete",
        views.offering_service_ticket_delete_form_submit,
        name="offerings-service-ticket-delete",
    ),
    path(
        "<str:offering_id>/documents/new",
        views.offering_document_form_submit,
        name="offerings-document-create",
    ),
    path(
        "<str:offering_id>/documents/<int:document_id>/edit",
        views.offering_document_edit_form_submit,
        name="offerings-document-edit",
    ),
    path(
        "<str:offering_id>/documents/<int:document_id>/delete",
        views.offering_document_delete_form_submit,
        name="offerings-document-delete",
    ),
]

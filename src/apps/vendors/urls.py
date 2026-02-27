from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.vendors import views

urlpatterns = [
    # HTML Pages
    path("", views.vendor_list_page, name="vendors-list"),
    path("new", views.vendor_form_page, name="vendors-create"),
    path("<str:vendor_id>", views.vendor_detail_page, name="vendors-detail"),
    path("<str:vendor_id>/edit", views.vendor_form_page, name="vendors-edit"),
    
    # HTML Pages: Vendor Contacts
    path(
        "<str:vendor_id>/contacts",
        views.vendor_contact_list_page,
        name="vendor_contact_list"
    ),
    path(
        "<str:vendor_id>/contacts/new",
        views.vendor_contact_form_page,
        name="vendor_contact_create"
    ),
    path(
        "<str:vendor_id>/contacts/<int:contact_id>/edit",
        views.vendor_contact_form_page,
        name="vendor_contact_edit"
    ),
    path(
        "<str:vendor_id>/contacts/<int:contact_id>/delete",
        views.vendor_contact_delete_page,
        name="vendor_contact_delete"
    ),
    
    # HTML Pages: Vendor Identifiers
    path(
        "<str:vendor_id>/identifiers",
        views.vendor_identifier_list_page,
        name="vendor_identifier_list"
    ),
    path(
        "<str:vendor_id>/identifiers/new",
        views.vendor_identifier_form_page,
        name="vendor_identifier_create"
    ),
    path(
        "<str:vendor_id>/identifiers/<int:identifier_id>/edit",
        views.vendor_identifier_form_page,
        name="vendor_identifier_edit"
    ),
    path(
        "<str:vendor_id>/identifiers/<int:identifier_id>/delete",
        views.vendor_identifier_delete_page,
        name="vendor_identifier_delete"
    ),
    
    # API endpoint for AJAX detail loading
    path("api/<str:vendor_id>/details", views.vendor_detail_api, name="vendors-detail-api"),
    
    # API: Vendor Contacts
    path(
        "api/<str:vendor_id>/contacts",
        views.vendor_contacts_endpoint,
        name="vendors-contacts-list"
    ),
    path(
        "api/<str:vendor_id>/contacts/<int:contact_id>",
        views.vendor_contact_detail_endpoint,
        name="vendors-contact-detail"
    ),
    
    # API: Vendor Identifiers
    path(
        "api/<str:vendor_id>/identifiers",
        views.vendor_identifiers_endpoint,
        name="vendors-identifiers-list"
    ),
    path(
        "api/<str:vendor_id>/identifiers/<int:identifier_id>",
        views.vendor_identifier_detail_endpoint,
        name="vendors-identifier-detail"
    ),
    
    # API: Vendor Onboarding Workflow
    path(
        "api/<str:vendor_id>/workflow",
        views.onboarding_workflow_endpoint,
        name="vendors-workflow"
    ),
    path(
        "api/<str:vendor_id>/workflow/status",
        views.onboarding_workflow_detail_endpoint,
        name="vendors-workflow-status"
    ),
]
# ============================================================================
# DRF REST API Routes
# ============================================================================

router = DefaultRouter()

# Main resource routers
router.register(r'api/v1/vendors', views.VendorAPIViewSet, basename='vendor-api')
router.register(r'api/v1/vendor-contacts', views.VendorContactAPIViewSet, basename='vendor-contact-api')
router.register(r'api/v1/vendor-identifiers', views.VendorIdentifierAPIViewSet, basename='vendor-identifier-api')
router.register(r'api/v1/onboarding-workflows', views.OnboardingWorkflowAPIViewSet, basename='onboarding-workflow-api')

# Vendor metadata and tracking
router.register(r'api/v1/vendor-notes', views.VendorNoteAPIViewSet, basename='vendor-note-api')
router.register(r'api/v1/vendor-warnings', views.VendorWarningAPIViewSet, basename='vendor-warning-api')
router.register(r'api/v1/vendor-tickets', views.VendorTicketAPIViewSet, basename='vendor-ticket-api')
router.register(r'api/v1/vendor-business-owners', views.VendorBusinessOwnerAPIViewSet, basename='vendor-business-owner-api')
router.register(r'api/v1/vendor-org-assignments', views.VendorOrgAssignmentAPIViewSet, basename='vendor-org-assignment-api')

# Offering tracking
router.register(r'api/v1/offering-notes', views.OfferingNoteAPIViewSet, basename='offering-note-api')
router.register(r'api/v1/offering-tickets', views.OfferingTicketAPIViewSet, basename='offering-ticket-api')

# Contracts and events
router.register(r'api/v1/contract-events', views.ContractEventAPIViewSet, basename='contract-event-api')

# Vendor demos and scoring
router.register(r'api/v1/vendor-demos', views.VendorDemoAPIViewSet, basename='vendor-demo-api')
router.register(r'api/v1/demo-scores', views.DemoScoreAPIViewSet, basename='demo-score-api')
router.register(r'api/v1/demo-notes', views.DemoNoteAPIViewSet, basename='demo-note-api')

urlpatterns.extend([
    path('', include(router.urls)),
])
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.contracts import views as contracts_views
from apps.core import api as core_api
from apps.core import views as core_views
from apps.demos import views as demos_views
from apps.help_center import views as help_center_views
from apps.imports import views as imports_views
from apps.offerings import views as offerings_views
from apps.projects import views as projects_views
from apps.reports import views as reports_views
from apps.vendors import views as vendors_views
from apps.workflows import views as workflows_views

urlpatterns = [
    path("", core_views.home_redirect, name="home"),
    path("dashboard", core_views.dashboard, name="dashboard"),
    path("vendor-360/", include("apps.vendors.urls")),
    path("projects/", include("apps.projects.urls")),
    path("imports/", include("apps.imports.urls")),
    path("offerings/", include("apps.offerings.urls")),
    path("workflows/", include("apps.workflows.urls")),
    path("reports/", include("apps.reports.urls")),
    path("admin/", include("apps.admin_portal.urls")),
    path("contracts/", include("apps.contracts.urls")),
    path("demos/", include("apps.demos.urls")),
    path("help/", include("apps.help_center.urls")),
    path("access/", include("apps.identity.ui_urls")),
    path("pending-approvals/", include("apps.identity.pending_ui_urls")),
    path("api/v1/identity", include("apps.identity.urls")),
    path("api/v1/access/", include("apps.identity.access_urls")),
    path("api/v1/pending-approvals/", include("apps.identity.pending_api_urls")),
    path("api/v1/admin/", include("apps.admin_portal.api_urls")),
    path("api/v1/vendors", vendors_views.vendor_collection_endpoint, name="api-vendors-collection"),
    path("api/v1/vendors/<str:vendor_id>", vendors_views.update_vendor_endpoint, name="api-vendors-update"),
    path("api/v1/vendors/merge/preview", vendors_views.merge_vendors_preview_endpoint, name="api-vendors-merge-preview"),
    path("api/v1/vendors/merge/execute", vendors_views.merge_vendors_execute_endpoint, name="api-vendors-merge-execute"),
    path("api/v1/search/vendors", vendors_views.search_vendors_endpoint, name="api-search-vendors"),
    path("api/v1/search/offerings", vendors_views.search_offerings_endpoint, name="api-search-offerings"),
    path("api/v1/search/projects", vendors_views.search_projects_endpoint, name="api-search-projects"),
    path("api/v1/search/contracts", vendors_views.search_contracts_endpoint, name="api-search-contracts"),
    path("api/v1/search/users", vendors_views.search_users_endpoint, name="api-search-users"),
    path("api/v1/search/contacts", vendors_views.search_contacts_endpoint, name="api-search-contacts"),
    path("api/v1/projects", projects_views.project_collection_endpoint, name="api-projects-collection"),
    path(
        "api/v1/projects/<str:project_id>/sections",
        projects_views.project_sections_endpoint,
        name="api-project-sections",
    ),
    path(
        "api/v1/projects/<str:project_id>/sections/<str:section_key>/requests",
        projects_views.project_section_change_request_endpoint,
        name="api-project-section-change-request",
    ),
    path("api/v1/projects/<str:project_id>", projects_views.update_project_endpoint, name="api-projects-update"),
    path(
        "api/v1/vendors/<str:vendor_id>/contracts",
        contracts_views.vendor_contracts_endpoint,
        name="api-vendor-contracts",
    ),
    path(
        "api/v1/contracts/<str:contract_id>",
        contracts_views.contract_detail_endpoint,
        name="api-contract-detail",
    ),
    path(
        "api/v1/vendors/<str:vendor_id>/offerings",
        offerings_views.vendor_offerings_endpoint,
        name="api-vendor-offerings",
    ),
    path(
        "api/v1/offerings/<str:offering_id>",
        offerings_views.offering_detail_endpoint,
        name="api-offering-detail",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/contacts",
        offerings_views.offering_contacts_endpoint,
        name="api-offering-contacts",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/contacts/<int:contact_id>",
        offerings_views.offering_contact_detail_endpoint,
        name="api-offering-contact-detail",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/contracts",
        offerings_views.offering_contracts_endpoint,
        name="api-offering-contracts",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/data-flows",
        offerings_views.offering_data_flows_endpoint,
        name="api-offering-data-flows",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/data-flows/<int:flow_id>",
        offerings_views.offering_data_flow_detail_endpoint,
        name="api-offering-data-flow-detail",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/service-tickets",
        offerings_views.offering_service_tickets_endpoint,
        name="api-offering-service-tickets",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/service-tickets/<int:ticket_id>",
        offerings_views.offering_service_ticket_detail_endpoint,
        name="api-offering-service-ticket-detail",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/documents",
        offerings_views.offering_documents_endpoint,
        name="api-offering-documents",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/documents/<int:document_id>",
        offerings_views.offering_document_detail_endpoint,
        name="api-offering-document-detail",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/program-profile",
        offerings_views.offering_program_profile_endpoint,
        name="api-offering-program-profile",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/entitlements",
        offerings_views.offering_entitlements_endpoint,
        name="api-offering-entitlements",
    ),
    path(
        "api/v1/offerings/<str:offering_id>/entitlements/<int:entitlement_id>",
        offerings_views.offering_entitlement_detail_endpoint,
        name="api-offering-entitlement-detail",
    ),
    path("api/v1/demos", demos_views.demos_collection_endpoint, name="api-demos-collection"),
    path("api/v1/demos/<str:demo_id>", demos_views.demo_detail_endpoint, name="api-demos-detail"),
    path("api/v1/imports/jobs", imports_views.import_jobs_collection_endpoint, name="api-import-jobs-collection"),
    path("api/v1/imports/jobs/<str:import_job_id>", imports_views.import_job_detail_endpoint, name="api-import-job-detail"),
    path(
        "api/v1/imports/jobs/<str:import_job_id>/preview",
        imports_views.import_job_preview_endpoint,
        name="api-import-job-preview",
    ),
    path(
        "api/v1/imports/jobs/<str:import_job_id>/mapping",
        imports_views.import_job_mapping_endpoint,
        name="api-import-job-mapping",
    ),
    path(
        "api/v1/imports/jobs/<str:import_job_id>/stage",
        imports_views.import_job_stage_endpoint,
        name="api-import-job-stage",
    ),
    path(
        "api/v1/imports/jobs/<str:import_job_id>/review",
        imports_views.import_job_review_endpoint,
        name="api-import-job-review",
    ),
    path(
        "api/v1/imports/jobs/<str:import_job_id>/apply",
        imports_views.import_job_apply_endpoint,
        name="api-import-job-apply",
    ),
    path(
        "api/v1/workflows/decisions",
        workflows_views.workflow_decisions_collection_endpoint,
        name="api-workflow-decisions-collection",
    ),
    path(
        "api/v1/workflows/decisions/open-next",
        workflows_views.workflow_decisions_open_next_endpoint,
        name="api-workflow-decisions-open-next",
    ),
    path(
        "api/v1/workflows/decisions/<str:decision_id>",
        workflows_views.workflow_decision_detail_endpoint,
        name="api-workflow-decision-detail",
    ),
    path(
        "api/v1/workflows/decisions/<str:decision_id>/transition",
        workflows_views.workflow_decision_transition_endpoint,
        name="api-workflow-decision-transition",
    ),
    path("api/v1/reports/runs", reports_views.report_runs_collection_endpoint, name="api-report-runs-collection"),
    path("api/v1/reports/runs/<str:report_run_id>", reports_views.report_run_detail_endpoint, name="api-report-run-detail"),
    path("api/v1/reports/runs/<str:run_id>/download", reports_views.report_run_download_endpoint, name="api-report-run-download"),
    path("api/v1/reports/email-requests", reports_views.report_email_request_endpoint, name="api-report-email-request"),
    path("api/v1/help/articles", help_center_views.help_articles_collection_endpoint, name="api-help-articles-collection"),
    path("api/v1/help/articles/<slug:slug>", help_center_views.help_article_by_slug_endpoint, name="api-help-article-by-slug"),
    path("api/v1/help/articles/<str:article_id>/", help_center_views.help_article_detail_endpoint, name="api-help-article-detail"),
    path("api/v1/help/search", help_center_views.help_search_endpoint, name="api-help-search"),
    path("api/v1/help/feedback", help_center_views.help_feedback_endpoint, name="api-help-feedback"),
    path("api/v1/help/issues", help_center_views.help_issue_endpoint, name="api-help-issues"),
    path("api/v1/health/live", core_api.health_live, name="health-live"),
    path("api/v1/health/ready", core_api.health_ready, name="health-ready"),
    path("api/v1/health", core_api.health, name="health"),
    path("api/v1/runtime", core_api.runtime_metadata, name="runtime-metadata"),
    path("api/v1/observability", core_api.observability_metadata, name="observability-metadata"),
    path("api/v1/metrics", core_api.metrics_payload, name="metrics"),
    path("api/v1/diagnostics/bootstrap", core_api.diagnostics_bootstrap, name="diagnostics-bootstrap"),
    path("_django_admin/", admin.site.urls),
]

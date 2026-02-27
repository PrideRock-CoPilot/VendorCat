from __future__ import annotations

from apps.core.contracts.policy import PermissionDecision, PolicySnapshot
from apps.core.services.policy_engine import PolicyEngine

# Contract map for mutation endpoints in the rebuild architecture.
MUTATION_PERMISSION_MAP: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/vendors"): "vendor.write",
    ("PATCH", "/api/v1/vendors/{vendor_id}"): "vendor.write",
    ("POST", "/api/v1/vendors/{vendor_id}/contacts"): "vendor.write",
    ("PATCH", "/api/v1/vendors/{vendor_id}/contacts/{contact_id}"): "vendor.write",
    ("DELETE", "/api/v1/vendors/{vendor_id}/contacts/{contact_id}"): "vendor.write",
    ("POST", "/api/v1/vendors/{vendor_id}/identifiers"): "vendor.write",
    ("PATCH", "/api/v1/vendors/{vendor_id}/identifiers/{identifier_id}"): "vendor.write",
    ("DELETE", "/api/v1/vendors/{vendor_id}/identifiers/{identifier_id}"): "vendor.write",
    ("POST", "/api/v1/vendors/{vendor_id}/workflow"): "vendor.write",
    ("PATCH", "/api/v1/vendors/{vendor_id}/workflow"): "vendor.write",
    ("POST", "/api/v1/vendors/merge/preview"): "vendor.write",
    ("POST", "/api/v1/vendors/merge/execute"): "vendor.write",
    ("POST", "/api/v1/projects"): "project.write",
    ("PATCH", "/api/v1/projects/{project_id}"): "project.write",
    ("POST", "/api/v1/projects/{project_id}/sections/{section_key}/requests"): "project.write",
    ("POST", "/api/v1/vendors/{vendor_id}/offerings"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}"): "offering.write",
    ("POST", "/api/v1/offerings/{offering_id}/contacts"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}/contacts/{contact_id}"): "offering.write",
    ("DELETE", "/api/v1/offerings/{offering_id}/contacts/{contact_id}"): "offering.write",
    ("POST", "/api/v1/offerings/{offering_id}/contracts"): "contract.write",
    ("POST", "/api/v1/offerings/{offering_id}/data-flows"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}/data-flows/{flow_id}"): "offering.write",
    ("DELETE", "/api/v1/offerings/{offering_id}/data-flows/{flow_id}"): "offering.write",
    ("POST", "/api/v1/offerings/{offering_id}/service-tickets"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}/service-tickets/{ticket_id}"): "offering.write",
    ("DELETE", "/api/v1/offerings/{offering_id}/service-tickets/{ticket_id}"): "offering.write",
    ("POST", "/api/v1/offerings/{offering_id}/documents"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}/documents/{document_id}"): "offering.write",
    ("DELETE", "/api/v1/offerings/{offering_id}/documents/{document_id}"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}/program-profile"): "offering.write",
    ("POST", "/api/v1/offerings/{offering_id}/entitlements"): "offering.write",
    ("PATCH", "/api/v1/offerings/{offering_id}/entitlements/{entitlement_id}"): "offering.write",
    ("DELETE", "/api/v1/offerings/{offering_id}/entitlements/{entitlement_id}"): "offering.write",
    ("POST", "/api/v1/vendors/{vendor_id}/contracts"): "contract.write",
    ("PATCH", "/api/v1/contracts/{contract_id}"): "contract.write",
    ("POST", "/api/v1/demos"): "demo.write",
    ("PATCH", "/api/v1/demos/{demo_id}"): "demo.write",
    ("POST", "/api/v1/imports/jobs"): "import.run",
    ("PATCH", "/api/v1/imports/jobs/{import_job_id}"): "import.run",
    ("POST", "/api/v1/workflows/decisions"): "workflow.run",
    ("PATCH", "/api/v1/workflows/decisions/{decision_id}"): "workflow.run",
    ("POST", "/api/v1/workflows/decisions/{decision_id}/transition"): "workflow.run",
    ("POST", "/api/v1/reports/runs"): "report.run",
    ("PATCH", "/api/v1/reports/runs/{report_run_id}"): "report.run",
    ("POST", "/api/v1/reports/email-requests"): "report.email_request",
    ("POST", "/api/v1/help/articles"): "help.write",
    ("PATCH", "/api/v1/help/articles/{article_id}"): "help.write",
    ("POST", "/api/v1/help/feedback"): "help.feedback.write",
    ("POST", "/api/v1/help/issues"): "help.issue.write",
    ("POST", "/api/v1/access/requests"): "access.request",
    ("POST", "/api/v1/access/requests/review"): "access.review",
    ("POST", "/api/v1/access/terms/accept"): "terms.accept",
    ("POST", "/api/v1/admin/roles/assign"): "access.review",
    ("POST", "/api/v1/admin/roles/revoke"): "access.review",
    ("POST", "/api/v1/admin/groups/assign"): "access.review",
    ("POST", "/api/v1/admin/groups/revoke"): "access.review",
    ("POST", "/api/v1/admin/scopes/grant"): "access.review",
    ("POST", "/api/v1/admin/scopes/revoke"): "access.review",
    ("POST", "/api/v1/pending-approvals/queue/open-next"): "access.review",
    ("POST", "/api/v1/pending-approvals/queue/decision"): "access.review",
    ("POST", "/api/v1/imports/jobs/{import_job_id}/preview"): "import.run",
    ("POST", "/api/v1/imports/jobs/{import_job_id}/mapping"): "import.run",
    ("POST", "/api/v1/imports/jobs/{import_job_id}/stage"): "import.run",
    ("POST", "/api/v1/imports/jobs/{import_job_id}/review"): "import.run",
    ("POST", "/api/v1/imports/jobs/{import_job_id}/apply"): "import.run",
}

READ_PERMISSION_MAP: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/reports/runs"): "report.read",
    ("GET", "/api/v1/reports/runs/{report_run_id}"): "report.read",
    ("GET", "/api/v1/reports/runs/{run_id}/download"): "report.read",
    ("GET", "/api/v1/help/articles/{slug}"): "help.read",
    ("GET", "/api/v1/help/search"): "help.read",
    ("GET", "/api/v1/metrics"): "observability.read",
    ("GET", "/api/v1/diagnostics/bootstrap"): "observability.read",
}


def permission_for_mutation(method: str, path_template: str) -> str:
    key = (method.upper(), path_template)
    if key not in MUTATION_PERMISSION_MAP:
        raise KeyError(f"No permission mapping for {key}")
    return MUTATION_PERMISSION_MAP[key]


def authorize_mutation(snapshot: PolicySnapshot, method: str, path_template: str) -> PermissionDecision:
    permission = permission_for_mutation(method, path_template)
    return PolicyEngine.decide(snapshot, permission)


def permission_for_read(method: str, path_template: str) -> str:
    key = (method.upper(), path_template)
    if key not in READ_PERMISSION_MAP:
        raise KeyError(f"No read permission mapping for {key}")
    return READ_PERMISSION_MAP[key]

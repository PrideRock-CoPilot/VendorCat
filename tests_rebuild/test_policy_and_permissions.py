from __future__ import annotations

from apps.core.contracts.policy import PolicySnapshot
from apps.core.services.permission_registry import (
    MUTATION_PERMISSION_MAP,
    authorize_mutation,
    permission_for_mutation,
)
from apps.core.services.policy_engine import PolicyEngine


def test_policy_engine_grants_editor_permissions() -> None:
    snapshot = PolicySnapshot(user_principal="editor@example.com", roles=("vendor_editor",), scopes=())
    decision = PolicyEngine.decide(snapshot, "import.run")
    assert decision.allowed is True


def test_policy_engine_denies_missing_permissions() -> None:
    snapshot = PolicySnapshot(user_principal="viewer@example.com", roles=("vendor_viewer",), scopes=())
    decision = PolicyEngine.decide(snapshot, "vendor.write")
    assert decision.allowed is False


def test_permission_registry_contains_required_routes() -> None:
    assert ("POST", "/api/v1/imports/jobs") in MUTATION_PERMISSION_MAP
    assert permission_for_mutation("POST", "/api/v1/vendors") == "vendor.write"
    assert permission_for_mutation("POST", "/api/v1/access/requests") == "access.request"
    assert permission_for_mutation("POST", "/api/v1/access/requests/review") == "access.review"
    assert permission_for_mutation("POST", "/api/v1/access/terms/accept") == "terms.accept"
    assert permission_for_mutation("POST", "/api/v1/reports/email-requests") == "report.email_request"
    assert permission_for_mutation("POST", "/api/v1/help/feedback") == "help.feedback.write"
    assert permission_for_mutation("POST", "/api/v1/help/issues") == "help.issue.write"


def test_authorize_mutation_uses_registry_contract() -> None:
    snapshot = PolicySnapshot(user_principal="approver@example.com", roles=("workflow_reviewer",), scopes=())
    decision = authorize_mutation(snapshot, "POST", "/api/v1/workflows/decisions")
    assert decision.allowed is True

    review_decision = authorize_mutation(snapshot, "POST", "/api/v1/access/requests/review")
    assert review_decision.allowed is True

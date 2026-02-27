from __future__ import annotations

from apps.core.contracts.policy import PermissionDecision, PolicySnapshot

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "vendor_admin": {"*"},
    "vendor_editor": {
        "vendor.write",
        "project.write",
        "offering.write",
        "contract.write",
        "contract.read",
        "demo.write",
        "import.run",
        "report.run",
        "report.read",
        "report.email_request",
        "help.read",
        "help.write",
        "help.feedback.write",
        "help.issue.write",
    },
    "offering_editor": {
        "offering.write",
        "vendor.read",
        "project.read",
        "report.read",
        "help.read",
    },
    "workflow_reviewer": {"workflow.run", "access.review"},
    "ops_observer": {"observability.read"},
    "vendor_viewer": {"vendor.read", "project.read", "report.read", "help.read"},
    "authenticated": {"access.request", "terms.accept", "help.feedback.write", "help.issue.write"},
    "anonymous": set(),
}


class PolicyEngine:
    @staticmethod
    def decide(snapshot: PolicySnapshot, permission: str) -> PermissionDecision:
        for role in snapshot.roles:
            granted = ROLE_PERMISSIONS.get(role, set())
            if "*" in granted or permission in granted:
                return PermissionDecision(True, permission, f"granted by role={role}")
        return PermissionDecision(False, permission, "permission not granted")

from __future__ import annotations


class SchemaBootstrapRequiredError(RuntimeError):
    """Raised when required runtime schema objects are missing or inaccessible."""


class EmployeeDirectoryError(RuntimeError):
    """Raised when user is not found in the employee directory and cannot be bootstrapped."""

    def __init__(self, login_identifier: str, details: str = ""):
        self.login_identifier = login_identifier
        self.details = details
        super().__init__(
            f"Access cannot be bootstrapped: user '{login_identifier}' is not in the employee directory."
        )

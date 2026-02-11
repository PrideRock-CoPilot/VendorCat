from __future__ import annotations


class SchemaBootstrapRequiredError(RuntimeError):
    """Raised when required runtime schema objects are missing or inaccessible."""

"""Core application configuration and shared constants."""

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.core.repository_errors import SchemaBootstrapRequiredError

__all__ = ["AppConfig", "SchemaBootstrapRequiredError"]

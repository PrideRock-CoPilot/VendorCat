from __future__ import annotations

"""Compatibility exports for repository APIs.

This module intentionally re-exports ``VendorRepository`` and core constants
so existing imports continue to work while backend internals are modularized.
"""

from vendor_catalog_app.backend.repository import VendorRepository
from vendor_catalog_app.core.repository_constants import *  # noqa: F403
from vendor_catalog_app.core.repository_errors import SchemaBootstrapRequiredError


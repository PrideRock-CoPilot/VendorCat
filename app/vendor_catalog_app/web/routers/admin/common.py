from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from vendor_catalog_app.repository import (
    LOOKUP_TYPE_ASSIGNMENT_TYPE,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_DOC_SOURCE,
    LOOKUP_TYPE_DOC_TAG,
    LOOKUP_TYPE_OFFERING_LOB,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_PROJECT_TYPE,
    LOOKUP_TYPE_WORKFLOW_STATUS,
)


LOGGER = logging.getLogger(__name__)

ROLE_CODE_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_-]{2,63}$")
LOOKUP_CODE_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_-]{1,63}$")
ADMIN_SECTION_ACCESS = "access"
ADMIN_SECTION_DEFAULTS = "defaults"
LOOKUP_STATUS_OPTIONS = {"all", "active", "historical", "future"}
LOOKUP_TYPE_LABELS = {
    LOOKUP_TYPE_DOC_SOURCE: "Document Sources",
    LOOKUP_TYPE_DOC_TAG: "Document Tags",
    LOOKUP_TYPE_OWNER_ROLE: "Owner Roles",
    LOOKUP_TYPE_ASSIGNMENT_TYPE: "Assignment Types",
    LOOKUP_TYPE_CONTACT_TYPE: "Contact Types",
    LOOKUP_TYPE_PROJECT_TYPE: "Project Types",
    LOOKUP_TYPE_OFFERING_TYPE: "Offering Types",
    LOOKUP_TYPE_OFFERING_LOB: "Offering LOB",
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE: "Offering Service Types",
    LOOKUP_TYPE_WORKFLOW_STATUS: "Workflow Statuses",
}


def _admin_redirect_url(
    *,
    section: str,
    lookup_type: str | None = None,
    lookup_status: str | None = None,
    as_of: str | None = None,
) -> str:
    if section == ADMIN_SECTION_DEFAULTS:
        selected_lookup = lookup_type if lookup_type in LOOKUP_TYPE_LABELS else LOOKUP_TYPE_DOC_SOURCE
        selected_status = lookup_status if lookup_status in LOOKUP_STATUS_OPTIONS else "active"
        selected_as_of = str(as_of or "").strip() or datetime.now(timezone.utc).date().isoformat()
        return (
            f"/admin?section={ADMIN_SECTION_DEFAULTS}&lookup_type={selected_lookup}"
            f"&status={selected_status}&as_of={selected_as_of}"
        )
    return f"/admin?section={ADMIN_SECTION_ACCESS}"


def _normalize_admin_section(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in {ADMIN_SECTION_ACCESS, ADMIN_SECTION_DEFAULTS}:
        return value
    return ADMIN_SECTION_ACCESS


def _normalize_lookup_type(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in LOOKUP_TYPE_LABELS:
        return value
    return LOOKUP_TYPE_DOC_SOURCE


def _slug_lookup_code(value: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "").strip().lower())
    normalized = re.sub(r"[^a-z0-9_-]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _normalize_lookup_status(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in LOOKUP_STATUS_OPTIONS:
        return value
    return "active"


def _normalize_as_of_date(raw: str | None) -> str:
    value = str(raw or "").strip()
    if value:
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except Exception:
            LOGGER.debug("Invalid as_of date '%s'; falling back to current UTC date.", value, exc_info=True)
    return datetime.now(timezone.utc).date().isoformat()


def _date_value(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return raw[:10]

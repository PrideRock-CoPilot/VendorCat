from __future__ import annotations

import json
import re

from fastapi import Request

from vendor_catalog_app.env import TVENDOR_FORWARDED_GROUP_HEADERS, get_env
from vendor_catalog_app.web.core.runtime import get_config, trust_forwarded_identity_headers


DEFAULT_FORWARDED_GROUP_HEADERS = (
    "x-forwarded-groups",
    "x-forwarded-group",
    "x-databricks-groups",
)
GROUP_PRINCIPAL_PREFIX = "group:"
GROUP_PRINCIPAL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:@/-]{1,190}$")


def sanitize_header_identity_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any(ch in text for ch in ("\r", "\n", "\t", "\x00")):
        return ""
    if len(text) > 320:
        return ""
    return text


def _first_header(request: Request, names: list[str]) -> str:
    for name in names:
        raw = sanitize_header_identity_value(str(request.headers.get(name, "")))
        if raw:
            return raw
    return ""


def _forwarded_group_headers() -> list[str]:
    configured = get_env(TVENDOR_FORWARDED_GROUP_HEADERS, ",".join(DEFAULT_FORWARDED_GROUP_HEADERS))
    names: list[str] = []
    for raw_name in configured.split(","):
        name = sanitize_header_identity_value(raw_name).lower()
        if not name:
            continue
        if name not in names:
            names.append(name)
    return names or list(DEFAULT_FORWARDED_GROUP_HEADERS)


def _normalize_group_principal(raw_group: str) -> str:
    text = sanitize_header_identity_value(raw_group).lower()
    if not text:
        return ""
    if text.startswith(GROUP_PRINCIPAL_PREFIX):
        text = text[len(GROUP_PRINCIPAL_PREFIX) :]
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9._:@/-]", "_", text)
    text = re.sub(r"_+", "_", text).strip("._:/-")
    if not text or not GROUP_PRINCIPAL_PATTERN.match(text):
        return ""
    return f"{GROUP_PRINCIPAL_PREFIX}{text}"


def _group_candidates_from_header(raw_value: str) -> list[str]:
    value = sanitize_header_identity_value(raw_value)
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    return re.split(r"[;,]", value)


def resolve_databricks_request_group_principals(request: Request) -> set[str]:
    config = get_config()
    if not trust_forwarded_identity_headers(config):
        return set()
    groups: set[str] = set()
    for header_name in _forwarded_group_headers():
        header_value = str(request.headers.get(header_name, ""))
        for candidate in _group_candidates_from_header(header_value):
            group_principal = _normalize_group_principal(candidate)
            if group_principal:
                groups.add(group_principal)
    return groups


def _email_from_value(value: str) -> str:
    text = sanitize_header_identity_value(value)
    if not text or "@" not in text:
        return ""
    return text.lower()


def _network_id_from_value(value: str) -> str:
    text = sanitize_header_identity_value(value)
    if not text:
        return ""
    candidate = text.split("\\")[-1].split("/")[-1].strip()
    if "@" in candidate:
        candidate = candidate.split("@", 1)[0].strip()
    if not candidate:
        return ""
    if len(candidate) > 128:
        return ""
    return candidate


def _clean_name(value: str) -> str:
    text = sanitize_header_identity_value(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 120:
        return ""
    return text


def _split_name(display_name: str) -> tuple[str, str]:
    cleaned = _clean_name(display_name)
    if not cleaned:
        return "", ""
    parts = [part for part in cleaned.split(" ") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1].lower() == "user":
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def display_name_for_principal(user_principal: str) -> str:
    raw = str(user_principal or "").strip()
    if not raw:
        return "Unknown User"

    normalized = raw.split("\\")[-1].split("/")[-1]
    if "@" in normalized:
        normalized = normalized.split("@", 1)[0]
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    normalized = re.sub(r"[._-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return "Unknown User"

    parts = [part.capitalize() for part in normalized.split(" ") if part]
    if not parts:
        return "Unknown User"
    if len(parts) == 1:
        return f"{parts[0]} User"
    return " ".join(parts)


def resolve_databricks_request_identity(request: Request) -> dict[str, str]:
    config = get_config()
    if not trust_forwarded_identity_headers(config):
        return {
            "principal": "",
            "email": "",
            "network_id": "",
            "first_name": "",
            "last_name": "",
            "display_name": "",
        }

    email_header = _first_header(request, ["x-forwarded-email", "x-user-email"])
    preferred_username = _first_header(request, ["x-forwarded-preferred-username", "x-forwarded-upn"])
    forwarded_user = _first_header(request, ["x-forwarded-user"])
    forwarded_network_id = _first_header(
        request,
        ["x-forwarded-network-id", "x-forwarded-user-id", "x-databricks-user-id"],
    )
    given_name_header = _first_header(request, ["x-forwarded-given-name", "x-forwarded-first-name"])
    family_name_header = _first_header(request, ["x-forwarded-family-name", "x-forwarded-last-name"])
    display_name_header = _first_header(request, ["x-forwarded-name", "x-forwarded-display-name"])

    principal = (
        preferred_username
        or _email_from_value(email_header)
        or forwarded_user
        or _network_id_from_value(forwarded_network_id)
    )
    email = (
        _email_from_value(email_header)
        or _email_from_value(preferred_username)
        or _email_from_value(forwarded_user)
        or _email_from_value(principal)
    )
    network_id = (
        _network_id_from_value(forwarded_network_id)
        or _network_id_from_value(forwarded_user)
        or _network_id_from_value(preferred_username)
        or _network_id_from_value(email)
        or _network_id_from_value(principal)
    )

    first_name = _clean_name(given_name_header)
    last_name = _clean_name(family_name_header)
    display_name = _clean_name(display_name_header)
    if not display_name and (first_name or last_name):
        display_name = " ".join(part for part in (first_name, last_name) if part).strip()
    if not display_name:
        seed = preferred_username or forwarded_user or email or network_id or principal
        parsed_name = display_name_for_principal(seed)
        display_name = parsed_name if parsed_name != "Unknown User" else ""
    if not first_name and not last_name:
        first_name, last_name = _split_name(display_name)

    return {
        "principal": principal,
        "email": email,
        "network_id": network_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
    }

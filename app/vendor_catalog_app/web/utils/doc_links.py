from __future__ import annotations

import re
from urllib.parse import unquote, urlparse


DOC_TYPES = [
    "sharepoint",
    "onedrive",
    "confluence",
    "google_drive",
    "box",
    "dropbox",
    "github",
    "other",
]

DOC_TAG_OPTIONS = [
    "contract",
    "msa",
    "nda",
    "sow",
    "invoice",
    "renewal",
    "security",
    "architecture",
    "runbook",
    "compliance",
    "rfp",
    "poc",
    "notes",
    "operations",
    "folder",
]


def _normalized_link_value(doc_url: str) -> str:
    return re.sub(r"\s+", " ", str(doc_url or "").strip())


def _urlparse_flexible(link_value: str):
    raw = _normalized_link_value(link_value)
    if not raw:
        return urlparse("")
    if "://" in raw or raw.startswith("//"):
        return urlparse(raw)
    if raw.startswith("\\\\"):
        return urlparse(f"//{raw.lstrip('\\')}")
    return urlparse(f"//{raw}")


def _is_folder_like_link(link_value: str) -> bool:
    raw = _normalized_link_value(link_value)
    if not raw:
        return False
    if raw.endswith("/") or raw.endswith("\\"):
        return True

    parsed = _urlparse_flexible(raw)
    path = str(parsed.path or "")
    if "/folders/" in raw.lower():
        return True
    if path:
        tail = path.rstrip("/").split("/")[-1]
        if tail and "." not in tail and "/" in path:
            return True
    return False


def suggest_doc_type(doc_url: str) -> str:
    value = _normalized_link_value(doc_url).lower()
    if "sharepoint.com" in value or "/sites/" in value or "/teams/" in value:
        return "sharepoint"
    if "onedrive.live.com" in value or "1drv.ms" in value:
        return "onedrive"
    if "atlassian.net/wiki" in value or "/confluence" in value:
        return "confluence"
    if "docs.google.com" in value or "drive.google.com" in value:
        return "google_drive"
    if "box.com" in value and "dropbox.com" not in value:
        return "box"
    if "dropbox.com" in value:
        return "dropbox"
    if "github.com" in value:
        return "github"
    return "other"


def extract_doc_fqdn(doc_url: str) -> str:
    raw = _normalized_link_value(doc_url)
    if not raw:
        return ""

    parsed = _urlparse_flexible(raw)
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if host:
        return host

    token = re.split(r"[\\/\s]", raw, maxsplit=1)[0].strip().lower().rstrip(".")
    if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", token):
        return token
    return ""


def normalize_doc_fqdn(value: str) -> str:
    cleaned = (value or "").strip().lower().rstrip(".")
    if not cleaned:
        return ""
    if not re.fullmatch(r"[a-z0-9.-]+", cleaned):
        raise ValueError("FQDN can only include letters, numbers, dots, and hyphens.")
    if ".." in cleaned:
        raise ValueError("FQDN format is invalid.")
    return cleaned


def derive_doc_tags(doc_url: str) -> list[str]:
    tags: list[str] = []
    if _is_folder_like_link(doc_url):
        tags.append("folder")
    return tags


def normalize_doc_tags(
    raw_tags: list[str] | str | None,
    *,
    doc_type: str,
    fqdn: str,
    doc_url: str = "",
) -> list[str]:
    out: list[str] = []

    def _append(value: str) -> None:
        tag = (value or "").strip().lower()
        if not tag:
            return
        if tag.startswith("fqdn:"):
            suffix = normalize_doc_fqdn(tag.split(":", 1)[1])
            if not suffix:
                return
            fqdn_tag = f"fqdn:{suffix}"
            if fqdn_tag not in out:
                out.append(fqdn_tag)
            return
        tag = re.sub(r"\s+", "_", tag)
        tag = re.sub(r"[^a-z0-9:_-]", "_", tag)
        tag = re.sub(r"_+", "_", tag).strip("_")
        if not tag:
            return
        if tag not in out:
            out.append(tag)

    if isinstance(raw_tags, list):
        for value in raw_tags:
            for chunk in str(value).split(","):
                _append(chunk)
    elif isinstance(raw_tags, str):
        for value in raw_tags.split(","):
            _append(value)

    normalized_type = (doc_type or "").strip().lower()
    if normalized_type in DOC_TYPES:
        _append(normalized_type)

    for tag in derive_doc_tags(doc_url):
        _append(tag)

    normalized_fqdn = normalize_doc_fqdn(fqdn)
    if normalized_fqdn:
        _append(f"fqdn:{normalized_fqdn}")
    return out


def suggest_doc_title(doc_url: str) -> str:
    raw = _normalized_link_value(doc_url)
    parsed = _urlparse_flexible(raw)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        host = extract_doc_fqdn(raw) or "link"
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts and raw and host != "link":
        raw_suffix = raw
        lowered = raw.lower()
        if lowered.startswith(f"{host}/"):
            raw_suffix = raw[len(host) + 1 :]
        path_parts = [part for part in re.split(r"[\\/]+", raw_suffix) if part]
    last_segment = unquote(path_parts[-1]) if path_parts else ""
    if not last_segment:
        last_segment = "link"
    last_segment = re.sub(r"[\r\n\t]+", " ", last_segment)
    last_segment = re.sub(r"\s+", " ", last_segment).strip()
    last_segment = re.sub(r"[^A-Za-z0-9._ -]", "", last_segment)
    if not last_segment:
        last_segment = "link"
    title = f"{host} - {last_segment}"
    if len(title) > 120:
        title = title[:117].rstrip() + "..."
    return title

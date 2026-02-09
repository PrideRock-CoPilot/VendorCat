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


def suggest_doc_type(doc_url: str) -> str:
    value = (doc_url or "").strip().lower()
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


def suggest_doc_title(doc_url: str) -> str:
    parsed = urlparse((doc_url or "").strip())
    host = (parsed.hostname or "link").strip().lower()
    path_parts = [part for part in parsed.path.split("/") if part]
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

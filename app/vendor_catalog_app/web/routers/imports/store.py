from __future__ import annotations

from copy import deepcopy
import threading
import time
import uuid
from typing import Any


IMPORT_PREVIEW_TTL_SEC = 1800.0
IMPORT_PREVIEW_MAX_ITEMS = 64
IMPORT_PREVIEW_LOCK = threading.Lock()
_IMPORT_PREVIEW_STORE: dict[str, tuple[float, dict[str, Any]]] = {}


def _prune_preview_store(now: float) -> None:
    expired = [token for token, (created, _) in _IMPORT_PREVIEW_STORE.items() if (now - created) >= IMPORT_PREVIEW_TTL_SEC]
    for token in expired:
        _IMPORT_PREVIEW_STORE.pop(token, None)
    while len(_IMPORT_PREVIEW_STORE) > IMPORT_PREVIEW_MAX_ITEMS:
        oldest_token = min(_IMPORT_PREVIEW_STORE, key=lambda key: _IMPORT_PREVIEW_STORE[key][0], default=None)
        if oldest_token is None:
            break
        _IMPORT_PREVIEW_STORE.pop(oldest_token, None)


def save_preview_payload(payload: dict[str, Any]) -> str:
    token = uuid.uuid4().hex
    now = time.monotonic()
    with IMPORT_PREVIEW_LOCK:
        _prune_preview_store(now)
        _IMPORT_PREVIEW_STORE[token] = (now, deepcopy(payload))
    return token


def load_preview_payload(token: str) -> dict[str, Any] | None:
    key = str(token or "").strip()
    if not key:
        return None
    now = time.monotonic()
    with IMPORT_PREVIEW_LOCK:
        _prune_preview_store(now)
        entry = _IMPORT_PREVIEW_STORE.get(key)
        if entry is None:
            return None
        _, payload = entry
        return deepcopy(payload)


def discard_preview_payload(token: str) -> None:
    key = str(token or "").strip()
    if not key:
        return
    with IMPORT_PREVIEW_LOCK:
        _IMPORT_PREVIEW_STORE.pop(key, None)


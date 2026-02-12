from __future__ import annotations

import hmac
import secrets
import threading
import time
from collections import deque
from urllib.parse import urlparse

from fastapi import Request

CSRF_SESSION_KEY = "tvendor_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER = "x-csrf-token"
UNSAFE_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _sanitize_identity_value(value: str, *, max_len: int = 320) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any(ch in text for ch in ("\r", "\n", "\t", "\x00")):
        return ""
    if len(text) > max_len:
        return ""
    return text


def request_requires_write_protection(method: str) -> bool:
    return str(method or "").upper() in UNSAFE_HTTP_METHODS


def ensure_csrf_token(request: Request, *, session_key: str = CSRF_SESSION_KEY) -> str:
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return ""
    token = str(session.get(session_key, "")).strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    session[session_key] = token
    return token


def _is_same_origin(request: Request) -> bool:
    request_origin = f"{request.url.scheme}://{request.url.netloc}".lower()
    origin = _sanitize_identity_value(str(request.headers.get("origin", ""))).lower()
    if origin:
        return origin == request_origin

    referer = _sanitize_identity_value(str(request.headers.get("referer", "")))
    if not referer:
        return False
    parsed = urlparse(referer)
    referer_origin = f"{parsed.scheme}://{parsed.netloc}".lower()
    return bool(parsed.scheme and parsed.netloc and referer_origin == request_origin)


def _is_form_content_type(content_type: str) -> bool:
    normalized = str(content_type or "").lower()
    return ("application/x-www-form-urlencoded" in normalized) or ("multipart/form-data" in normalized)


async def request_matches_csrf_token(
    request: Request,
    *,
    expected_token: str,
    header_name: str = CSRF_HEADER,
    form_field_name: str = CSRF_FORM_FIELD,
) -> bool:
    expected = str(expected_token or "").strip()
    if not expected:
        return False

    header_value = str(request.headers.get(header_name, "")).strip()
    if header_value and hmac.compare_digest(header_value, expected):
        return True

    content_type = str(request.headers.get("content-type", ""))
    if _is_form_content_type(content_type):
        try:
            form = await request.form()
            form_value = str(form.get(form_field_name, "")).strip()
            if form_value and hmac.compare_digest(form_value, expected):
                return True
        except Exception:
            return False

    # Fallback for no-JS or legacy clients: enforce same-origin checks.
    return _is_same_origin(request)


def request_rate_limit_key(request: Request) -> str:
    client_host = str(getattr(getattr(request, "client", None), "host", "")).strip()
    if client_host:
        return f"ip:{client_host}"
    return "ip:unknown"


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        enabled: bool,
        max_requests: int,
        window_seconds: int,
        max_keys: int = 10000,
    ) -> None:
        self._enabled = bool(enabled)
        self._max_requests = max(1, int(max_requests))
        self._window_seconds = max(1, int(window_seconds))
        self._max_keys = max(128, int(max_keys))
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = {}
        self._last_seen: dict[str, float] = {}

    def allow(self, key: str) -> tuple[bool, int]:
        if not self._enabled:
            return True, 0
        normalized_key = _sanitize_identity_value(str(key or ""), max_len=512) or "anonymous"
        now = time.monotonic()
        cutoff = now - float(self._window_seconds)
        with self._lock:
            samples = self._events.get(normalized_key)
            if samples is None:
                samples = deque()
                self._events[normalized_key] = samples
            while samples and samples[0] <= cutoff:
                samples.popleft()

            if len(samples) >= self._max_requests:
                retry_after = max(1, int((samples[0] + float(self._window_seconds)) - now))
                self._last_seen[normalized_key] = now
                self._trim_locked(now)
                return False, retry_after

            samples.append(now)
            self._last_seen[normalized_key] = now
            self._trim_locked(now)
            return True, 0

    def _trim_locked(self, now: float) -> None:
        if len(self._events) <= self._max_keys:
            return

        cutoff = now - float(self._window_seconds)
        stale_keys: list[str] = []
        for key, samples in self._events.items():
            while samples and samples[0] <= cutoff:
                samples.popleft()
            if not samples:
                stale_keys.append(key)
        for key in stale_keys:
            self._events.pop(key, None)
            self._last_seen.pop(key, None)

        while len(self._events) > self._max_keys:
            oldest_key = min(self._last_seen, key=self._last_seen.get, default=None)
            if oldest_key is None:
                break
            self._events.pop(oldest_key, None)
            self._last_seen.pop(oldest_key, None)

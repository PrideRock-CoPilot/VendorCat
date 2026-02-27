from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.core.observability import METRICS

LOGGER = logging.getLogger("vendorcatalog.rebuild")


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = str(request.headers.get("X-Request-ID") or uuid.uuid4())
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class StructuredRequestLogMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        METRICS.observe_http(request.path, request.method, response.status_code, elapsed_ms)
        request_id = getattr(request, "request_id", "")
        LOGGER.info(
            "request_completed method=%s path=%s status=%s elapsed_ms=%.2f request_id=%s",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

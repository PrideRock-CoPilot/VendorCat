from __future__ import annotations

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from apps.core.contracts.errors import ApiErrorPayload

LOGGER = logging.getLogger("vendorcatalog.rebuild")


class UnifiedErrorMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except Exception:  # pragma: no cover - exercised by integration behavior
            request_id = str(getattr(request, "request_id", ""))
            LOGGER.exception("request_failed request_id=%s path=%s", request_id, request.path)
            if request.path.startswith("/api/"):
                payload = ApiErrorPayload(
                    code="internal_error",
                    message="An internal error occurred.",
                    request_id=request_id,
                )
                return JsonResponse(payload.to_dict(), status=500)
            return render(
                request,
                "shared/error.html",
                {
                    "page_title": "Error",
                    "error_message": "An internal error occurred.",
                    "request_id": request_id,
                },
                status=500,
            )

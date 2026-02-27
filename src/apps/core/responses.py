from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, JsonResponse

from apps.core.contracts.errors import ApiErrorPayload


def parse_json_body(request: HttpRequest) -> dict[str, Any]:
    raw = request.body.decode("utf-8") if request.body else ""
    if not raw.strip():
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def api_error(
    request: HttpRequest,
    *,
    code: str,
    message: str,
    status: int,
    details: tuple[str, ...] = (),
) -> JsonResponse:
    request_id = str(getattr(request, "request_id", ""))
    payload = ApiErrorPayload(code=code, message=message, request_id=request_id, details=details)
    return JsonResponse(payload.to_dict(), status=status)


def api_json(payload: dict[str, Any], status: int = 200) -> JsonResponse:
    return JsonResponse(payload, status=status)

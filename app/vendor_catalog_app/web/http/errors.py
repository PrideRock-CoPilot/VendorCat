from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vendor_catalog_app.core.env import TVENDOR_ERROR_INCLUDE_DETAILS, get_env_bool
from vendor_catalog_app.core.repository_errors import SchemaBootstrapRequiredError
from vendor_catalog_app.infrastructure.db import DataConnectionError, DataExecutionError, DataQueryError

ERROR_CODE_SCHEMA_BOOTSTRAP_REQUIRED = "SCHEMA_BOOTSTRAP_REQUIRED"
ERROR_CODE_VALIDATION = "VALIDATION_ERROR"
ERROR_CODE_BAD_REQUEST = "BAD_REQUEST"
ERROR_CODE_NOT_FOUND = "NOT_FOUND"
ERROR_CODE_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_CODE_FORBIDDEN = "FORBIDDEN"
ERROR_CODE_DB_CONNECTION = "DB_CONNECTION_ERROR"
ERROR_CODE_DB_QUERY = "DB_QUERY_ERROR"
ERROR_CODE_DB_EXECUTION = "DB_EXECUTION_ERROR"
ERROR_CODE_INTERNAL = "INTERNAL_SERVER_ERROR"


@dataclass(frozen=True)
class ApiErrorSpec:
    status_code: int
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        self.details = details


def is_api_request(request: Request) -> bool:
    path = str(getattr(request.url, "path", "") or "")
    return path.startswith("/api/")


def request_id_from_request(request: Request) -> str:
    try:
        request_id = str(getattr(request.state, "request_id", "") or "").strip()
    except Exception:
        request_id = ""
    if request_id:
        return request_id
    from_header = str(request.headers.get("x-request-id", "")).strip()
    return from_header or "-"


def _include_details() -> bool:
    return get_env_bool(TVENDOR_ERROR_INCLUDE_DETAILS, default=False)


def build_api_error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": str(code),
            "message": str(message),
        },
        "request_id": str(request_id or "-"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if details and _include_details():
        payload["error"]["details"] = details
    return payload


def api_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = request_id_from_request(request)
    payload = build_api_error_payload(
        code=code,
        message=message,
        request_id=request_id,
        details=details,
    )
    headers = {"X-Request-ID": request_id}
    return JSONResponse(payload, status_code=int(status_code), headers=headers)


def normalize_exception(exc: Exception) -> ApiErrorSpec:
    if isinstance(exc, ApiError):
        return ApiErrorSpec(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    if isinstance(exc, RequestValidationError):
        return ApiErrorSpec(
            status_code=422,
            code=ERROR_CODE_VALIDATION,
            message="Request validation failed. Check field values and try again.",
            details={"errors": exc.errors()},
        )

    if isinstance(exc, SchemaBootstrapRequiredError):
        return ApiErrorSpec(
            status_code=503,
            code=ERROR_CODE_SCHEMA_BOOTSTRAP_REQUIRED,
            message="Application schema is not ready. Complete bootstrap and retry.",
            details={"reason": str(exc)},
        )

    if isinstance(exc, DataConnectionError):
        return ApiErrorSpec(
            status_code=503,
            code=ERROR_CODE_DB_CONNECTION,
            message="Database connection is unavailable. Please try again shortly.",
            details={"reason": str(exc)},
        )

    if isinstance(exc, DataQueryError):
        return ApiErrorSpec(
            status_code=500,
            code=ERROR_CODE_DB_QUERY,
            message="Failed to execute the requested query.",
            details={"reason": str(exc)},
        )

    if isinstance(exc, DataExecutionError):
        return ApiErrorSpec(
            status_code=500,
            code=ERROR_CODE_DB_EXECUTION,
            message="Failed to execute the requested update.",
            details={"reason": str(exc)},
        )

    if isinstance(exc, PermissionError):
        return ApiErrorSpec(
            status_code=403,
            code=ERROR_CODE_FORBIDDEN,
            message="You do not have permission to perform this action.",
            details={"reason": str(exc)},
        )

    if isinstance(exc, ValueError):
        return ApiErrorSpec(
            status_code=400,
            code=ERROR_CODE_BAD_REQUEST,
            message=str(exc) or "Request parameters are invalid.",
            details={"reason": str(exc)},
        )

    if isinstance(exc, StarletteHTTPException):
        code = ERROR_CODE_INTERNAL
        if exc.status_code == 400:
            code = ERROR_CODE_BAD_REQUEST
        elif exc.status_code == 401:
            code = ERROR_CODE_UNAUTHORIZED
        elif exc.status_code == 403:
            code = ERROR_CODE_FORBIDDEN
        elif exc.status_code == 404:
            code = ERROR_CODE_NOT_FOUND
        elif exc.status_code == 422:
            code = ERROR_CODE_VALIDATION
        return ApiErrorSpec(
            status_code=int(exc.status_code),
            code=code,
            message=str(exc.detail or "HTTP request failed."),
            details={"reason": str(exc.detail or "")},
        )

    return ApiErrorSpec(
        status_code=500,
        code=ERROR_CODE_INTERNAL,
        message="An unexpected error occurred. Please contact support if this continues.",
        details={"reason": str(exc), "type": exc.__class__.__name__},
    )

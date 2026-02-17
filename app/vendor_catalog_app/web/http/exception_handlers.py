from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from vendor_catalog_app.core.repository_errors import EmployeeDirectoryError, SchemaBootstrapRequiredError
from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.http.errors import ApiError, api_error_response, is_api_request, normalize_exception
from vendor_catalog_app.web.system.bootstrap_diagnostics import (
    bootstrap_diagnostics_authorized,
    build_bootstrap_diagnostics_payload,
)

LOGGER = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.exception_handler(SchemaBootstrapRequiredError)
    async def _schema_bootstrap_exception_handler(request: Request, exc: SchemaBootstrapRequiredError):
        if is_api_request(request):
            spec = normalize_exception(exc)
            return api_error_response(
                request,
                status_code=spec.status_code,
                code=spec.code,
                message=spec.message,
                details=spec.details,
            )
        try:
            repo = get_repo()
            config = get_config()
            if bootstrap_diagnostics_authorized(request, config):
                identity = resolve_databricks_request_identity(request)
                diagnostics, _status_code = build_bootstrap_diagnostics_payload(repo, config, identity)
                return templates.TemplateResponse(
                    request,
                    "bootstrap_diagnostics.html",
                    {
                        "request": request,
                        "diagnostics": diagnostics,
                        "error_message": str(exc),
                    },
                    status_code=503,
                )
        except Exception:
            pass
        return templates.TemplateResponse(
            request,
            "bootstrap_required.html",
            {"request": request, "error_message": str(exc)},
            status_code=503,
        )

    @app.exception_handler(EmployeeDirectoryError)
    async def _employee_directory_exception_handler(request: Request, exc: EmployeeDirectoryError):
        if is_api_request(request):
            return api_error_response(
                request,
                status_code=403,
                code="EMPLOYEE_DIRECTORY_NOT_FOUND",
                message=str(exc),
                details={"login_identifier": exc.login_identifier, "guidance": exc.details},
            )
        return templates.TemplateResponse(
            request,
            "user_directory_error.html",
            {
                "request": request,
                "login_identifier": exc.login_identifier,
                "error_message": str(exc),
                "guidance": exc.details,
            },
            status_code=403,
        )

    @app.exception_handler(ApiError)
    async def _api_error_exception_handler(request: Request, exc: ApiError):
        if not is_api_request(request):
            return PlainTextResponse(str(exc), status_code=exc.status_code)
        spec = normalize_exception(exc)
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error_handler(request: Request, exc: RequestValidationError):
        if not is_api_request(request):
            return await request_validation_exception_handler(request, exc)
        spec = normalize_exception(exc)
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(request: Request, exc: StarletteHTTPException):
        if not is_api_request(request):
            if int(getattr(exc, "status_code", 500) or 500) == 404:
                return templates.TemplateResponse(
                    request,
                    "404.html",
                    {
                        "request": request,
                        "missing_path": str(request.url.path or "/"),
                    },
                    status_code=404,
                )
            return await http_exception_handler(request, exc)
        spec = normalize_exception(exc)
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        if not is_api_request(request):
            LOGGER.exception(
                "Unhandled web request error. path=%s method=%s",
                request.url.path,
                request.method,
                extra={
                    "event": "unhandled_web_error",
                    "request_id": str(getattr(request.state, "request_id", "-")),
                    "method": request.method,
                    "path": str(request.url.path),
                },
            )
            return PlainTextResponse("An unexpected error occurred.", status_code=500)

        spec = normalize_exception(exc)
        log_fn = LOGGER.warning if spec.status_code < 500 else LOGGER.exception
        log_fn(
            "API request failed. code=%s status=%s path=%s method=%s",
            spec.code,
            spec.status_code,
            request.url.path,
            request.method,
            extra={
                "event": "api_error",
                "request_id": str(getattr(request.state, "request_id", "-")),
                "error_code": spec.code,
                "status_code": int(spec.status_code),
                "method": request.method,
                "path": str(request.url.path),
            },
        )
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

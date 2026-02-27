from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from vendor_catalog_app.infrastructure.logging import setup_app_logging
from vendor_catalog_app.infrastructure.observability import get_observability_manager
from vendor_catalog_app.web.core.runtime import get_config
from vendor_catalog_app.web.http.exception_handlers import register_exception_handlers
from vendor_catalog_app.web.http.middleware import (
    register_request_perf_middleware,
    register_security_headers_middleware,
)
from vendor_catalog_app.web.routers import router as web_router
from vendor_catalog_app.web.system.lifespan import create_app_lifespan
from vendor_catalog_app.web.system.metrics import register_prometheus_metrics_route
from vendor_catalog_app.web.system.settings import load_app_runtime_settings


def _extract_role_from_json(payload_json_str: str | dict) -> str:
    """Extract role from change request payload JSON."""
    try:
        if isinstance(payload_json_str, dict):
            payload = payload_json_str
        else:
            payload = json.loads(payload_json_str) if payload_json_str else {}
        return payload.get("role", "Unknown")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return "Unknown"


def _format_date(dt_obj) -> str:
    """Format datetime object for template display."""
    if not dt_obj:
        return ""
    if isinstance(dt_obj, str):
        try:
            dt_obj = datetime.fromisoformat(dt_obj.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return str(dt_obj)
    if isinstance(dt_obj, datetime):
        return dt_obj.strftime("%B %d, %Y at %I:%M %p")
    return str(dt_obj)


def create_app() -> FastAPI:
    setup_app_logging()
    config = get_config()
    settings = load_app_runtime_settings(config)

    app = FastAPI(title="Vendor Catalog", lifespan=create_app_lifespan(settings))
    observability = get_observability_manager()
    app.state.startup_splash_run_id = uuid.uuid4().hex

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    
    # Register custom Jinja2 filters
    templates.env.filters["extract_role"] = _extract_role_from_json
    templates.env.filters["format_date"] = _format_date
    
    app.state.templates = templates

    register_security_headers_middleware(app, settings)
    register_request_perf_middleware(app, settings, observability)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=settings.session_https_only,
    )

    register_prometheus_metrics_route(
        app,
        observability,
        metrics_allow_unauthenticated=settings.metrics_allow_unauthenticated,
        metrics_auth_token=settings.metrics_auth_token,
    )
    register_exception_handlers(app, templates)

    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(web_router)
    return app


app = create_app()


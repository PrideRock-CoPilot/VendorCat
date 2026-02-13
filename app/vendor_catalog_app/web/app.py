from __future__ import annotations

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


def create_app() -> FastAPI:
    setup_app_logging()
    config = get_config()
    settings = load_app_runtime_settings(config)

    app = FastAPI(title="Vendor Catalog", lifespan=create_app_lifespan(settings))
    observability = get_observability_manager()

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
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


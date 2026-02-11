from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.bootstrap_diagnostics import build_bootstrap_diagnostics_payload
from vendor_catalog_app.web.routers import router as web_router
from vendor_catalog_app.web.services import get_config, get_repo, resolve_databricks_request_identity


def create_app() -> FastAPI:
    app = FastAPI(title="Vendor Catalog")
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("TVENDOR_SESSION_SECRET", "vendor-catalog-dev-secret"),
        same_site="lax",
        https_only=False,
    )

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    app.state.templates = templates

    @app.exception_handler(SchemaBootstrapRequiredError)
    async def _schema_bootstrap_exception_handler(request: Request, exc: SchemaBootstrapRequiredError):
        try:
            repo = get_repo()
            config = get_config()
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

    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(web_router)
    return app


app = create_app()

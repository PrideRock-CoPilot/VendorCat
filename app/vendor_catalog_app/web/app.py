from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from vendor_catalog_app.web.routers import router as web_router


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
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(web_router)
    return app


app = create_app()


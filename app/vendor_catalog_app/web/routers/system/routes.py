from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.system.access_requests import router as access_requests_router
from vendor_catalog_app.web.routers.system.api_health import router as api_health_router
from vendor_catalog_app.web.routers.system.api_search import router as api_search_router
from vendor_catalog_app.web.routers.system.connection_lab import router as connection_lab_router
from vendor_catalog_app.web.routers.system.diagnostics_pages import router as diagnostics_pages_router

router = APIRouter()
router.include_router(api_health_router)
router.include_router(api_search_router)
router.include_router(access_requests_router)
router.include_router(diagnostics_pages_router)
router.include_router(connection_lab_router)

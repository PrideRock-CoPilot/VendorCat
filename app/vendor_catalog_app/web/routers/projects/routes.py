from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.projects.pages import router as pages_router
from vendor_catalog_app.web.routers.projects.writes import router as writes_router

router = APIRouter()
router.include_router(pages_router)
router.include_router(writes_router)

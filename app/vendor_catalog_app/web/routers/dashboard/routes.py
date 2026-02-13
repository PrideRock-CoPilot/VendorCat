from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.dashboard.pages import router as pages_router
from vendor_catalog_app.web.routers.dashboard.splash import router as splash_router


router = APIRouter()
router.include_router(splash_router)
router.include_router(pages_router)


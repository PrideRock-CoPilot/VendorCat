from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.imports.actions import router as actions_router
from vendor_catalog_app.web.routers.imports.pages import router as pages_router


router = APIRouter()
router.include_router(pages_router)
router.include_router(actions_router)

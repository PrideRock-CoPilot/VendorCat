from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.contracts.actions import router as actions_router
from vendor_catalog_app.web.routers.contracts.pages import router as pages_router

router = APIRouter()
router.include_router(pages_router)
router.include_router(actions_router)


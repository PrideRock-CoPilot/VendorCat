from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.projects.association_writes import router as association_writes_router
from vendor_catalog_app.web.routers.projects.content_writes import router as content_writes_router
from vendor_catalog_app.web.routers.projects.project_writes import router as project_writes_router

router = APIRouter()
router.include_router(project_writes_router)
router.include_router(association_writes_router)
router.include_router(content_writes_router)

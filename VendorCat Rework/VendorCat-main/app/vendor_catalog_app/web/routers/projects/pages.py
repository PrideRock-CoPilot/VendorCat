from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.projects.project_pages import router as project_pages_router
from vendor_catalog_app.web.routers.projects.section_pages import router as section_pages_router

router = APIRouter()
router.include_router(project_pages_router)
router.include_router(section_pages_router)

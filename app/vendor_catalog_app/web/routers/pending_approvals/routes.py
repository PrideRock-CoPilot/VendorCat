from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.pending_approvals.decisions import router as decisions_router
from vendor_catalog_app.web.routers.pending_approvals.detail_pages import router as detail_pages_router
from vendor_catalog_app.web.routers.pending_approvals.queue_pages import router as queue_pages_router


router = APIRouter()
router.include_router(queue_pages_router)
router.include_router(detail_pages_router)
router.include_router(decisions_router)

from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.imports.actions import router as actions_router
from vendor_catalog_app.web.routers.imports.workflow_v4 import router as workflow_v4_router

router = APIRouter()
# Register legacy-compatible handlers first for shared endpoints like
# /imports/preview and /imports/apply, then layer v4 workflow endpoints.
router.include_router(actions_router)
router.include_router(workflow_v4_router)

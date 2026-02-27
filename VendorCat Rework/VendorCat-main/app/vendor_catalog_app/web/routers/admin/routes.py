from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.admin.import_mappings import router as import_mappings_router
from vendor_catalog_app.web.routers.admin.lookups import router as lookups_router
from vendor_catalog_app.web.routers.admin.ownership import router as ownership_router
from vendor_catalog_app.web.routers.admin.pages import router as pages_router
from vendor_catalog_app.web.routers.admin.roles import router as roles_router
from vendor_catalog_app.web.routers.admin.scopes import router as scopes_router
from vendor_catalog_app.web.routers.admin.terms import router as terms_router
from vendor_catalog_app.web.routers.admin.testing_role import router as testing_role_router

router = APIRouter()
router.include_router(pages_router)
router.include_router(roles_router)
router.include_router(scopes_router)
router.include_router(testing_role_router)
router.include_router(lookups_router)
router.include_router(ownership_router)
router.include_router(terms_router)
router.include_router(import_mappings_router)

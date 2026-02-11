from fastapi import APIRouter

from vendor_catalog_app.web.routers.api import router as api_router
from vendor_catalog_app.web.routers.admin import router as admin_router
from vendor_catalog_app.web.routers.contracts import router as contracts_router
from vendor_catalog_app.web.routers.dashboard import router as dashboard_router
from vendor_catalog_app.web.routers.diagnostics import router as diagnostics_router
from vendor_catalog_app.web.routers.demos import router as demos_router
from vendor_catalog_app.web.routers.projects import router as projects_router
from vendor_catalog_app.web.routers.reports import router as reports_router
from vendor_catalog_app.web.routers.vendors import router as vendors_router
from vendor_catalog_app.web.routers.workflows import router as workflows_router


router = APIRouter()
router.include_router(api_router)
router.include_router(diagnostics_router)
router.include_router(dashboard_router)
router.include_router(vendors_router)
router.include_router(projects_router)
router.include_router(workflows_router)
router.include_router(reports_router)
router.include_router(demos_router)
router.include_router(contracts_router)
router.include_router(admin_router)

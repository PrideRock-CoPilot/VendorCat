from fastapi import APIRouter

from vendor_catalog_app.web.routers.vendors.alias import router as alias_router
from vendor_catalog_app.web.routers.vendors.changes import router as changes_router
from vendor_catalog_app.web.routers.vendors.contracts import router as contracts_router
from vendor_catalog_app.web.routers.vendors.demos import router as demos_router
from vendor_catalog_app.web.routers.vendors.docs import router as docs_router
from vendor_catalog_app.web.routers.vendors.list_pages import router as list_pages_router
from vendor_catalog_app.web.routers.vendors.merge_center import router as merge_center_router
from vendor_catalog_app.web.routers.vendors.offering_pages import router as offering_pages_router
from vendor_catalog_app.web.routers.vendors.offering_profile_writes import router as offering_profile_writes_router
from vendor_catalog_app.web.routers.vendors.offering_writes import router as offering_writes_router
from vendor_catalog_app.web.routers.vendors.projects import router as projects_router
from vendor_catalog_app.web.routers.vendors.vendor_detail_pages import router as vendor_detail_pages_router

router = APIRouter()
router.include_router(alias_router)
router.include_router(list_pages_router)
router.include_router(merge_center_router)
router.include_router(vendor_detail_pages_router)
router.include_router(offering_pages_router)
router.include_router(projects_router)
router.include_router(docs_router)
router.include_router(changes_router)
router.include_router(contracts_router)
router.include_router(demos_router)
router.include_router(offering_writes_router)
router.include_router(offering_profile_writes_router)

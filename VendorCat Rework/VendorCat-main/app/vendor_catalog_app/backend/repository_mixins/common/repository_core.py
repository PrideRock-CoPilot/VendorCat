from __future__ import annotations

from vendor_catalog_app.backend.repository_mixins.common.core import (
    RepositoryCoreAuditMixin,
    RepositoryCoreCacheMixin,
    RepositoryCoreCanonicalMixin,
    RepositoryCoreFrameMixin,
    RepositoryCoreIdentityMixin,
    RepositoryCoreLookupMixin,
    RepositoryCoreSqlMixin,
)


class RepositoryCoreMixin(
    RepositoryCoreSqlMixin,
    RepositoryCoreCacheMixin,
    RepositoryCoreFrameMixin,
    RepositoryCoreLookupMixin,
    RepositoryCoreCanonicalMixin,
    RepositoryCoreIdentityMixin,
    RepositoryCoreAuditMixin,
):
    pass

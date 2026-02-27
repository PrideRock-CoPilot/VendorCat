from __future__ import annotations

from .project import (
    RepositoryProjectActivityMixin,
    RepositoryProjectCatalogMixin,
    RepositoryProjectDemoMixin,
    RepositoryProjectWriteMixin,
)


class RepositoryProjectMixin(
    RepositoryProjectCatalogMixin,
    RepositoryProjectWriteMixin,
    RepositoryProjectDemoMixin,
    RepositoryProjectActivityMixin,
):
    pass

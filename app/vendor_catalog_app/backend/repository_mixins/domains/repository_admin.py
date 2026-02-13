from __future__ import annotations

from .admin import (
    RepositoryAdminGrantMixin,
    RepositoryAdminPolicyMixin,
)


class RepositoryAdminMixin(
    RepositoryAdminPolicyMixin,
    RepositoryAdminGrantMixin,
):
    pass

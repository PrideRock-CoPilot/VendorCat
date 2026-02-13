from __future__ import annotations

from .offering import (
    RepositoryOfferingDataMixin,
    RepositoryOfferingReadMixin,
    RepositoryOfferingWriteMixin,
)


class RepositoryOfferingMixin(
    RepositoryOfferingDataMixin,
    RepositoryOfferingReadMixin,
    RepositoryOfferingWriteMixin,
):
    pass

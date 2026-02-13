from __future__ import annotations

from .reporting import (
    RepositoryReportingExecutiveMixin,
    RepositoryReportingPortfolioMixin,
    RepositoryReportingSearchMixin,
    RepositoryReportingVendorsMixin,
)


class RepositoryReportingMixin(
    RepositoryReportingExecutiveMixin,
    RepositoryReportingPortfolioMixin,
    RepositoryReportingSearchMixin,
    RepositoryReportingVendorsMixin,
):
    pass

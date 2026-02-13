from __future__ import annotations

from .workflow import (
    RepositoryWorkflowContractMixin,
    RepositoryWorkflowDemoMixin,
    RepositoryWorkflowRequestMixin,
)


class RepositoryWorkflowMixin(
    RepositoryWorkflowRequestMixin,
    RepositoryWorkflowDemoMixin,
    RepositoryWorkflowContractMixin,
):
    pass

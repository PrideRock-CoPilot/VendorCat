from __future__ import annotations

import logging

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryWorkflowContractMixin:
    def contract_cancellations(self) -> pd.DataFrame:
        return self._cached(
            ("contract_cancellations",),
            lambda: self.client.query(
                self._sql(
                    "reporting/contract_cancellations.sql",
                    rpt_contract_cancellations=self._table("rpt_contract_cancellations"),
                )
            ),
            ttl_seconds=120,
        )


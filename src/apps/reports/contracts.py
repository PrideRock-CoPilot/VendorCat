from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ReportRunRequest:
    report_code: str
    filters: dict[str, str | int | float | bool | None]
    output_format: Literal["preview", "csv"]
    requested_by: str

    def validate(self) -> None:
        if not self.report_code.strip():
            raise ValueError("report_code is required")
        if self.output_format not in {"preview", "csv"}:
            raise ValueError("output_format must be preview or csv")
        if not self.requested_by.strip():
            raise ValueError("requested_by is required")


@dataclass(frozen=True)
class ReportRunResult:
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    row_count: int
    download_url: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ReportEmailRequest:
    run_id: str
    email_to: tuple[str, ...]
    requested_by: str

    def validate(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id is required")
        if not self.requested_by.strip():
            raise ValueError("requested_by is required")
        if not self.email_to:
            raise ValueError("email_to must include at least one recipient")

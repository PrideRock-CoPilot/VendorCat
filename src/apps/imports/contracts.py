from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportJobRequest:
    source_system: str
    source_object: str
    file_name: str
    submitted_by: str
    mapping_profile: str | None = None

    def validate(self) -> None:
        if not self.source_system.strip():
            raise ValueError("source_system is required")
        if not self.file_name.strip():
            raise ValueError("file_name is required")
        if not self.submitted_by.strip():
            raise ValueError("submitted_by is required")


@dataclass(frozen=True)
class ImportPreview:
    job_id: str
    total_rows: int
    blocked_rows: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportApplyRequest:
    job_id: str
    approved_by: str
    include_row_ids: tuple[str, ...] = field(default_factory=tuple)
    force_apply: bool = False

    def validate(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id is required")
        if not self.approved_by.strip():
            raise ValueError("approved_by is required")


@dataclass(frozen=True)
class ImportResult:
    job_id: str
    applied_rows: int
    blocked_rows: int
    status: str
    messages: tuple[str, ...] = ()

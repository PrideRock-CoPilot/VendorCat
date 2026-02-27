from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VendorRecord:
    vendor_id: str
    legal_name: str
    display_name: str
    lifecycle_state: str


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    project_name: str
    owner_principal: str


@dataclass(frozen=True)
class ImportJobRecord:
    import_job_id: str
    source_system: str
    file_name: str
    status: str


@dataclass(frozen=True)
class UserDirectoryRecord:
    user_id: str
    user_principal: str
    display_name: str
    email: str
    active_flag: bool


@dataclass(frozen=True)
class ReportRunRecord:
    run_id: str
    report_code: str
    status: str
    row_count: int


@dataclass(frozen=True)
class HelpArticleRecord:
    article_id: str
    slug: str
    title: str
    published: bool


class VendorRepository(Protocol):
    def get(self, vendor_id: str) -> VendorRecord | None:
        ...


class ProjectRepository(Protocol):
    def get(self, project_id: str) -> ProjectRecord | None:
        ...


class ImportRepository(Protocol):
    def get_job(self, import_job_id: str) -> ImportJobRecord | None:
        ...


class UserDirectoryRepository(Protocol):
    def upsert(self, principal: str, display_name: str, email: str | None) -> UserDirectoryRecord:
        ...


class ReportRepository(Protocol):
    def create_run(self, report_code: str, requested_by: str, output_format: str) -> ReportRunRecord:
        ...

    def get_run(self, run_id: str) -> ReportRunRecord | None:
        ...


class HelpCenterRepository(Protocol):
    def get_article(self, slug: str) -> HelpArticleRecord | None:
        ...

    def search(self, query: str) -> list[HelpArticleRecord]:
        ...

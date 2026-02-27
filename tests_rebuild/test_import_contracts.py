from __future__ import annotations

from apps.imports.contracts import ImportApplyRequest, ImportJobRequest


def test_import_job_request_requires_source_system() -> None:
    request = ImportJobRequest(
        source_system="",
        source_object="supplier",
        file_name="vendors.csv",
        submitted_by="owner@example.com",
    )

    try:
        request.validate()
    except ValueError as exc:
        assert "source_system" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_import_apply_request_requires_job_and_approver() -> None:
    request = ImportApplyRequest(job_id="job-1", approved_by="owner@example.com")
    request.validate()

    bad_request = ImportApplyRequest(job_id="", approved_by="owner@example.com")
    try:
        bad_request.validate()
    except ValueError as exc:
        assert "job_id" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

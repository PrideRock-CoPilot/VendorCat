from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db


def test_perf_baseline_script_generates_markdown_report(tmp_path: Path) -> None:
    output_file = tmp_path / "perf_report.md"

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "src")
    env.setdefault("DJANGO_SETTINGS_MODULE", "vendorcatalog_rebuild.settings")
    env.setdefault("VC_RUNTIME_PROFILE", "local")
    env.setdefault("VC_LOCAL_DUCKDB_PATH", str(tmp_path / "perf.duckdb"))

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rebuild/perf_baseline.py",
            "--iterations",
            "3",
            "--output",
            str(output_file),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "Performance Baseline Report" in content
    assert "| search |" in content
    assert "| import_preview |" in content
    assert "| report_preview |" in content

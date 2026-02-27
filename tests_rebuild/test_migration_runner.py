from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from apps.core.migrations.run_clean_rebuild import run_clean_rebuild


def test_clean_rebuild_runner_creates_local_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "rebuild.duckdb"
    monkeypatch.setenv("VC_RUNTIME_PROFILE", "local")
    monkeypatch.setenv("VC_LOCAL_DUCKDB_PATH", str(db_path))

    run_clean_rebuild()

    assert db_path.exists()
    with duckdb.connect(str(db_path)) as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'vc_vendor'"
        ).fetchone()
    assert result is not None
    table_count = int(result[0])
    assert table_count == 1

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_local_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "tvendor_local.db"
    init_script = repo_root / "setup" / "local_db" / "init_local_db.py"
    result = subprocess.run(
        [
            sys.executable,
            str(init_script),
            "--db-path",
            str(db_path),
            "--reset",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to initialize isolated local DB for tests.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    monkeypatch.setenv("TVENDOR_ENV", "dev")
    monkeypatch.setenv("TVENDOR_USE_LOCAL_DB", "true")
    monkeypatch.setenv("TVENDOR_LOCAL_DB_PATH", str(db_path))
    monkeypatch.setenv("TVENDOR_TEST_USER", "admin@example.com")
    monkeypatch.setenv("TVENDOR_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("TVENDOR_TERMS_ENFORCEMENT_ENABLED", "false")
    return db_path

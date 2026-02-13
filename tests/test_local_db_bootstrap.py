from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import vendor_catalog_app.infrastructure.local_db_bootstrap as bootstrap
from vendor_catalog_app.core.config import AppConfig


def _config(db_path: Path, use_local_db: bool = True) -> AppConfig:
    return AppConfig(
        databricks_server_hostname="",
        databricks_http_path="",
        databricks_token="",
        use_local_db=use_local_db,
        local_db_path=str(db_path),
        env="dev",
        catalog="a1_dlk",
        schema="twvendor",
    )


def test_bootstrap_skips_when_not_local_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called = {"value": False}

    def _fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(bootstrap.subprocess, "run", _fake_run)
    bootstrap.ensure_local_db_ready(_config(tmp_path / "db.sqlite", use_local_db=False))
    assert called["value"] is False


def test_bootstrap_skips_when_db_exists_and_no_reset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("", encoding="utf-8")
    called = {"value": False}

    def _fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(bootstrap.subprocess, "run", _fake_run)
    monkeypatch.delenv("TVENDOR_LOCAL_DB_RESET_ON_START", raising=False)
    bootstrap.ensure_local_db_ready(_config(db_path))
    assert called["value"] is False


def test_bootstrap_runs_init_script_for_missing_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite"
    captured: dict[str, object] = {}

    class _Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Result()

    monkeypatch.setattr(bootstrap.subprocess, "run", _fake_run)
    monkeypatch.delenv("TVENDOR_LOCAL_DB_SEED", raising=False)
    monkeypatch.delenv("TVENDOR_LOCAL_DB_RESET_ON_START", raising=False)

    bootstrap.ensure_local_db_ready(_config(db_path))

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "--db-path" in cmd
    assert str(db_path) in cmd
    assert "--skip-seed" in cmd


def test_bootstrap_raises_on_init_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite"

    class _Result:
        returncode = 1
        stdout = "failed"
        stderr = "traceback"

    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *args, **kwargs: _Result())

    with pytest.raises(RuntimeError, match="Local DB bootstrap failed"):
        bootstrap.ensure_local_db_ready(_config(db_path))

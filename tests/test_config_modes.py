from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.config import AppConfig


def _clear_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("TVENDOR_ENV", "TVENDOR_USE_LOCAL_DB", "TVENDOR_USE_MOCK"):
        monkeypatch.delenv(key, raising=False)


def test_dev_defaults_to_local_db(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "dev")

    config = AppConfig.from_env()

    assert config.env == "dev"
    assert config.is_dev_env is True
    assert config.use_local_db is True


def test_prod_defaults_to_databricks_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")

    config = AppConfig.from_env()

    assert config.env == "prod"
    assert config.is_dev_env is False
    assert config.use_local_db is False


def test_prod_rejects_local_db_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_USE_LOCAL_DB", "true")

    with pytest.raises(RuntimeError):
        AppConfig.from_env()

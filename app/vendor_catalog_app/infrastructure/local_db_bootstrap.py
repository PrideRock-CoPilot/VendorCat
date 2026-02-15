from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.core.env import (
    TVENDOR_LOCAL_DB_AUTO_INIT,
    TVENDOR_LOCAL_DB_RESET_ON_START,
    TVENDOR_LOCAL_DB_SEED,
    TVENDOR_LOCAL_DB_SEED_PROFILE,
    get_env,
    get_env_bool,
)


def ensure_local_db_ready(config: AppConfig) -> None:
    if not config.use_local_db:
        return

    auto_init = get_env_bool(TVENDOR_LOCAL_DB_AUTO_INIT, default=True)
    if not auto_init:
        return

    db_path = Path(config.local_db_path).resolve()
    reset_on_start = get_env_bool(TVENDOR_LOCAL_DB_RESET_ON_START, default=False)
    if db_path.exists() and not reset_on_start:
        return

    repo_root = Path(__file__).resolve().parents[3]
    init_script = (repo_root / "setup" / "local_db" / "init_local_db.py").resolve()
    if not init_script.exists():
        raise RuntimeError(f"Local DB init script not found: {init_script}")

    seed_on_init = get_env_bool(TVENDOR_LOCAL_DB_SEED, default=False)
    cmd = [
        sys.executable,
        str(init_script),
        "--db-path",
        str(db_path),
    ]
    if reset_on_start:
        cmd.append("--reset")
    if not seed_on_init:
        cmd.append("--skip-seed")
    else:
        seed_profile = str(get_env(TVENDOR_LOCAL_DB_SEED_PROFILE, "baseline") or "baseline").strip().lower()
        if seed_profile not in {"baseline", "full"}:
            seed_profile = "baseline"
        cmd.extend(["--seed-profile", seed_profile])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Local DB bootstrap failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, order=True)
class RouteKey:
    method: str
    path: str


def _load_app(app_root: Path):
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    spec = importlib.util.spec_from_file_location("old_main", app_root / "main.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load app module from {app_root / 'main.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def _route_keys(app) -> list[RouteKey]:
    keys: set[RouteKey] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            keys.add(RouteKey(str(method), str(path)))
    return sorted(keys)


def _write_text_manifest(path: Path, items: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(items) + "\n", encoding="utf-8")


def _iter_relative_files(root: Path, *, suffix: str | None = None) -> list[str]:
    out: list[str] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if suffix and file_path.suffix.lower() != suffix.lower():
            continue
        out.append(file_path.relative_to(root).as_posix())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate old-baseline parity manifests.")
    parser.add_argument(
        "--old-app-root",
        default=r"D:\VendorCatalog\archive\original-build\app",
        help="Path to old baseline app root (contains main.py).",
    )
    parser.add_argument(
        "--old-vendor-root",
        default=r"D:\VendorCatalog\archive\original-build\app\vendor_catalog_app",
        help="Path to old baseline vendor_catalog_app root.",
    )
    parser.add_argument(
        "--out-dir",
        default=r"D:\VendorCatalog\VendorCat Rework\VendorCat-main\tests\parity",
        help="Output directory for manifests.",
    )
    args = parser.parse_args()

    old_app_root = Path(args.old_app_root).resolve()
    old_vendor_root = Path(args.old_vendor_root).resolve()
    out_dir = Path(args.out_dir).resolve()

    old_app = _load_app(old_app_root)
    routes = _route_keys(old_app)

    route_manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "old_app_root": str(old_app_root),
        "routes": [{"method": key.method, "path": key.path} for key in routes],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "old_routes_manifest.json").write_text(
        json.dumps(route_manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    templates = _iter_relative_files(old_vendor_root / "web" / "templates", suffix=".html")
    _write_text_manifest(out_dir / "old_templates_manifest.txt", templates)

    static_files = _iter_relative_files(old_vendor_root / "web" / "static")
    _write_text_manifest(out_dir / "old_static_manifest.txt", static_files)

    sql_files = _iter_relative_files(old_vendor_root / "sql", suffix=".sql")
    _write_text_manifest(out_dir / "old_sql_manifest.txt", sql_files)

    print(f"Wrote {out_dir / 'old_routes_manifest.json'} with {len(routes)} routes")
    print(f"Wrote {out_dir / 'old_templates_manifest.txt'} with {len(templates)} templates")
    print(f"Wrote {out_dir / 'old_static_manifest.txt'} with {len(static_files)} static files")
    print(f"Wrote {out_dir / 'old_sql_manifest.txt'} with {len(sql_files)} SQL files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

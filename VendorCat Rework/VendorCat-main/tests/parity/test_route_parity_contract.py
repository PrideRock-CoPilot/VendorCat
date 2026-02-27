from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app  # noqa: E402


MANIFEST_PATH = Path(__file__).resolve().parent / "old_routes_manifest.json"


def _actual_routes() -> set[tuple[str, str]]:
    app = create_app()
    out: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            out.add((str(method), str(path)))
    return out


def _expected_routes() -> set[tuple[str, str]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    routes = payload.get("routes") or []
    return {
        (str(item.get("method") or "").upper(), str(item.get("path") or ""))
        for item in routes
        if item.get("method") and item.get("path")
    }


def test_route_parity_matches_old_manifest_exactly() -> None:
    expected = _expected_routes()
    actual = _actual_routes()

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)

    if missing or extra:
        details: list[str] = ["Route parity mismatch against old manifest."]
        if missing:
            details.append(f"Missing ({len(missing)}):")
            details.extend([f"  {method} {path}" for method, path in missing])
        if extra:
            details.append(f"Extra ({len(extra)}):")
            details.extend([f"  {method} {path}" for method, path in extra])
        raise AssertionError("\n".join(details))

from __future__ import annotations

import sys
from pathlib import Path

from starlette.requests import Request

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.http.errors import is_api_request  # noqa: E402


class _Route:
    def __init__(self, path: str) -> None:
        self.path = path


def _request(path: str, *, accept: str = "*/*", route_path: str = "") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "server": ("testserver", 443),
        "path": path,
        "query_string": b"",
        "headers": [(b"accept", accept.encode("utf-8"))],
    }
    if route_path:
        scope["route"] = _Route(route_path)

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, _receive)


def test_is_api_request_prefers_route_path_for_databricks_proxy_paths() -> None:
    request = _request(
        "/api/2.0/apps/abc123/vendorcatalog/dashboard",
        accept="text/html,application/xhtml+xml",
        route_path="/dashboard",
    )
    assert is_api_request(request) is False


def test_is_api_request_marks_real_api_route_even_with_html_accept() -> None:
    request = _request(
        "/api/2.0/apps/abc123/vendorcatalog/api/users/search",
        accept="text/html,application/xhtml+xml",
        route_path="/api/users/search",
    )
    assert is_api_request(request) is True


def test_is_api_request_accept_header_fallback_for_browser_navigation() -> None:
    request = _request(
        "/api/2.0/apps/abc123/vendorcatalog/dashboard",
        accept="text/html,application/xhtml+xml",
    )
    assert is_api_request(request) is False


def test_is_api_request_path_fallback_for_api_calls() -> None:
    request = _request("/api/users/search", accept="*/*")
    assert is_api_request(request) is True

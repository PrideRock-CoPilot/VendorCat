from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from vendor_catalog_app.web.system.settings import request_matches_token


def register_prometheus_metrics_route(
    app: FastAPI,
    observability,
    *,
    metrics_allow_unauthenticated: bool,
    metrics_auth_token: str,
) -> None:
    if not observability.prometheus_enabled:
        return

    @app.get(observability.prometheus_path, include_in_schema=False)
    async def _prometheus_metrics(request: Request) -> PlainTextResponse:
        if not metrics_allow_unauthenticated:
            if not metrics_auth_token or not request_matches_token(
                request,
                token=metrics_auth_token,
                header_name="x-tvendor-metrics-token",
            ):
                return PlainTextResponse("Not found.", status_code=404)
        return PlainTextResponse(
            observability.render_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

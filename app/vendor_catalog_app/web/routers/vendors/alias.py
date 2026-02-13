from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse


router = APIRouter()


@router.api_route("/vendor-360", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@router.api_route("/vendor-360/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def vendor360_alias(request: Request, path: str = ""):
    suffix = f"/{path}" if path else ""
    target = f"/vendors{suffix}"
    query = str(request.url.query or "").strip()
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target, status_code=307)

from __future__ import annotations

from typing import Any

from fastapi import Request


def add_flash(request: Request, message: str, level: str = "info") -> None:
    flashes = request.session.get("_flashes", [])
    flashes.append({"message": message, "level": level})
    request.session["_flashes"] = flashes


def pop_flashes(request: Request) -> list[dict[str, Any]]:
    flashes = request.session.get("_flashes", [])
    request.session["_flashes"] = []
    return flashes


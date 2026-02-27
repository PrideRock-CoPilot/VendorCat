from __future__ import annotations

from django.http import HttpRequest


def navigation_context(request: HttpRequest) -> dict[str, object]:
    return {
        "top_nav_items": [
            ("/dashboard", "Dashboard"),
            ("/vendor-360", "Vendor 360"),
            ("/projects", "Projects"),
            ("/offerings", "Offerings"),
            ("/contracts", "Contracts"),
            ("/demos", "Demos"),
            ("/imports", "Imports"),
            ("/workflows", "Workflows"),
            ("/reports", "Reports"),
            ("/help", "Help"),
            ("/admin", "Admin"),
        ],
        "active_path": request.path,
    }

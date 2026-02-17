from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.imports.parsing import (
    can_manage_imports,
    import_template_csv,
    render_context,
    safe_layout,
)

router = APIRouter()


def _imports_module():
    # Resolve through package namespace so tests can monkeypatch imports.get_repo/get_user_context.
    from vendor_catalog_app.web.routers import imports as imports_module

    return imports_module


@router.get("/imports")
def imports_home(request: Request):
    imports_module = _imports_module()
    imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")

    if not can_manage_imports(user):
        add_flash(request, "You do not have permission to access Imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra=render_context(selected_layout="vendors"),
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)


@router.get("/imports/templates/{layout_key}.csv")
def import_template_download(layout_key: str):
    selected_layout = safe_layout(layout_key)
    filename, content = import_template_csv(selected_layout)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


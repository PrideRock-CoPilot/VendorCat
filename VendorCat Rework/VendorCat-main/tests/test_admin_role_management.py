from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_admin_can_create_custom_role_and_use_testing_override(client: TestClient) -> None:
    save = client.post(
        "/admin/roles/save",
        data={
            "role_code": "vendor_note_editor",
            "role_name": "Vendor Note Editor",
            "description": "Can edit and submit notes.",
            "approval_level": "1",
            "can_edit": "on",
            "can_report": "on",
            "perm_add_project_note": "on",
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "vendor_note_editor" in admin_page.text

    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "vendor_note_editor", "return_to": "/vendors/new?return_to=%2Fvendors"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    with_override = client.get("/vendors/new?return_to=%2Fvendors")
    assert with_override.status_code == 200


def test_admin_can_grant_custom_role_to_user(client: TestClient) -> None:
    client.post(
        "/admin/roles/save",
        data={
            "role_code": "vendor_custom_reporter",
            "role_name": "Vendor Custom Reporter",
            "description": "Custom reporting role.",
            "approval_level": "0",
            "can_report": "on",
        },
        follow_redirects=False,
    )

    grant = client.post(
        "/admin/grant-role",
        data={"target_user": "owner@example.com", "role_code": "vendor_custom_reporter"},
        follow_redirects=False,
    )
    assert grant.status_code == 303

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "Owner User" in admin_page.text
    assert "vendor_custom_reporter" in admin_page.text


def test_admin_can_change_user_role_from_dropdown_flow(client: TestClient) -> None:
    client.post(
        "/admin/grant-role",
        data={"target_user": "pm@example.com", "role_code": "vendor_editor"},
        follow_redirects=False,
    )

    change = client.post(
        "/admin/change-role",
        data={
            "target_user": "pm@example.com",
            "current_role_code": "vendor_editor",
            "new_role_code": "vendor_auditor",
        },
        follow_redirects=False,
    )
    assert change.status_code == 303

    repo = get_repo()
    grants = repo.list_role_grants()
    user_rows = grants[grants["user_principal"].astype(str) == "pm@example.com"].copy()
    active_rows = user_rows[user_rows["active_flag"].astype(str).str.lower().isin({"1", "true"})]
    assert set(active_rows["role_code"].astype(str).tolist()) == {"vendor_auditor"}


def test_admin_grant_role_replaces_existing_active_role(client: TestClient) -> None:
    first_grant = client.post(
        "/admin/grant-role",
        data={"target_user": "owner@example.com", "role_code": "vendor_editor"},
        follow_redirects=False,
    )
    assert first_grant.status_code == 303

    second_grant = client.post(
        "/admin/grant-role",
        data={"target_user": "owner@example.com", "role_code": "vendor_admin"},
        follow_redirects=False,
    )
    assert second_grant.status_code == 303

    repo = get_repo()
    grants = repo.list_role_grants()
    user_rows = grants[grants["user_principal"].astype(str) == "owner@example.com"].copy()
    active_rows = user_rows[user_rows["active_flag"].astype(str).str.lower().isin({"1", "true"})]
    assert set(active_rows["role_code"].astype(str).tolist()) == {"vendor_admin"}


def test_admin_can_revoke_user_role_from_table_flow(client: TestClient) -> None:
    client.post(
        "/admin/grant-role",
        data={"target_user": "revoke.user@example.com", "role_code": "vendor_editor"},
        follow_redirects=False,
    )

    revoke = client.post(
        "/admin/revoke-role",
        data={"target_user": "revoke.user@example.com", "role_code": "vendor_editor"},
        follow_redirects=False,
    )
    assert revoke.status_code == 303

    repo = get_repo()
    grants = repo.list_role_grants()
    user_rows = grants[
        (grants["user_principal"].astype(str) == "revoke.user@example.com")
        & (grants["role_code"].astype(str) == "vendor_editor")
    ].copy()
    active_rows = user_rows[user_rows["active_flag"].astype(str).str.lower().isin({"1", "true"})]
    assert active_rows.empty


def test_admin_can_grant_role_to_group_and_group_member_inherits_it(client: TestClient) -> None:
    grant = client.post(
        "/admin/grant-group-role",
        data={"target_group": "AD-Vendor-Admins", "role_code": "vendor_admin"},
        follow_redirects=False,
    )
    assert grant.status_code == 303

    as_group_member = client.get(
        "/admin",
        headers={
            "x-forwarded-preferred-username": "group.member@example.com",
            "x-forwarded-groups": "AD-Vendor-Admins",
        },
    )
    assert as_group_member.status_code == 200
    assert "Admin Portal" in as_group_member.text
    assert "group:ad-vendor-admins" in as_group_member.text


def test_admin_can_change_group_role_from_table_flow(client: TestClient) -> None:
    client.post(
        "/admin/grant-group-role",
        data={"target_group": "AD-Role-Change", "role_code": "vendor_editor"},
        follow_redirects=False,
    )

    change = client.post(
        "/admin/change-group-role",
        data={
            "target_group": "AD-Role-Change",
            "current_role_code": "vendor_editor",
            "new_role_code": "vendor_auditor",
        },
        follow_redirects=False,
    )
    assert change.status_code == 303

    repo = get_repo()
    grants = repo.list_group_role_grants()
    group_rows = grants[grants["group_principal"].astype(str) == "group:ad-role-change"].copy()
    active_rows = group_rows[group_rows["active_flag"].astype(str).str.lower().isin({"1", "true"})]
    assert set(active_rows["role_code"].astype(str).tolist()) == {"vendor_auditor"}


def test_admin_can_revoke_group_role_from_table_flow(client: TestClient) -> None:
    client.post(
        "/admin/grant-group-role",
        data={"target_group": "AD-Role-Revoke", "role_code": "vendor_editor"},
        follow_redirects=False,
    )

    revoke = client.post(
        "/admin/revoke-group-role",
        data={"target_group": "AD-Role-Revoke", "role_code": "vendor_editor"},
        follow_redirects=False,
    )
    assert revoke.status_code == 303

    repo = get_repo()
    grants = repo.list_group_role_grants()
    group_rows = grants[
        (grants["group_principal"].astype(str) == "group:ad-role-revoke")
        & (grants["role_code"].astype(str) == "vendor_editor")
    ].copy()
    active_rows = group_rows[group_rows["active_flag"].astype(str).str.lower().isin({"1", "true"})]
    assert active_rows.empty


def test_admin_can_revoke_org_scope_from_table_flow(client: TestClient) -> None:
    client.post(
        "/admin/grant-scope",
        data={"target_user": "scope.user@example.com", "org_id": "IT-ENT", "scope_level": "edit"},
        follow_redirects=False,
    )

    revoke = client.post(
        "/admin/revoke-scope",
        data={"target_user": "scope.user@example.com", "org_id": "IT-ENT", "scope_level": "edit"},
        follow_redirects=False,
    )
    assert revoke.status_code == 303

    repo = get_repo()
    scopes = repo.list_scope_grants()
    user_rows = scopes[
        (scopes["user_principal"].astype(str) == "scope.user@example.com")
        & (scopes["org_id"].astype(str) == "IT-ENT")
        & (scopes["scope_level"].astype(str) == "edit")
    ].copy()
    active_rows = user_rows[user_rows["active_flag"].astype(str).str.lower().isin({"1", "true"})]
    assert active_rows.empty


def test_admin_can_add_doc_lookup_tag_and_use_in_doc_link(client: TestClient) -> None:
    save_lookup = client.post(
        "/admin/lookup/save",
        data={
            "lookup_type": "doc_tag",
            "option_code": "qbr",
            "option_label": "Quarterly Business Review",
            "sort_order": "55",
            "valid_from_ts": "2026-01-01",
            "valid_to_ts": "9999-12-31",
        },
        follow_redirects=False,
    )
    assert save_lookup.status_code == 303

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "qbr" in admin_page.text

    add_doc = client.post(
        "/vendors/vnd-001/docs/link",
        data={
            "return_to": "/vendors",
            "doc_url": "https://contoso.sharepoint.com/sites/vendors/qbr-2026.pdf",
            "doc_type": "sharepoint",
            "doc_title": "QBR 2026",
            "tags": ["qbr"],
            "owner": "admin@example.com",
        },
        follow_redirects=False,
    )
    assert add_doc.status_code == 303

    summary = client.get("/vendors/vnd-001/summary?return_to=%2Fvendors")
    assert summary.status_code == 200
    assert "QBR 2026" in summary.text
    assert "qbr" in summary.text


def test_admin_defaults_section_resequences_sort_order(client: TestClient) -> None:
    defaults_page = client.get("/admin?section=defaults&lookup_type=doc_tag")
    assert defaults_page.status_code == 200
    assert "Defaults Catalog" in defaults_page.text
    assert "Owner Roles" in defaults_page.text
    assert "Offering Types" in defaults_page.text

    create = client.post(
        "/admin/lookup/save",
        data={
            "lookup_type": "doc_tag",
            "option_code": "priority_review",
            "option_label": "Priority Review",
            "sort_order": "2",
            "valid_from_ts": "2026-01-01",
            "valid_to_ts": "9999-12-31",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303
    assert "section=defaults" in create.headers["location"]

    repo = get_repo()
    rows = repo.list_lookup_options("doc_tag", active_only=True)
    assert rows["sort_order"].tolist() == list(range(1, len(rows) + 1))
    priority_row = rows[rows["option_code"].astype(str) == "priority_review"].iloc[0]
    assert int(priority_row["sort_order"]) == 2

    move = client.post(
        "/admin/lookup/save",
        data={
            "lookup_type": "doc_tag",
            "option_id": str(priority_row["option_id"]),
            "option_code": "priority_review",
            "option_label": "Priority Review",
            "sort_order": "5",
            "valid_from_ts": "2026-01-01",
            "valid_to_ts": "9999-12-31",
        },
        follow_redirects=False,
    )
    assert move.status_code == 303

    moved = repo.list_lookup_options("doc_tag", active_only=True)
    assert moved["sort_order"].tolist() == list(range(1, len(moved) + 1))
    moved_priority = moved[moved["option_code"].astype(str) == "priority_review"].iloc[0]
    assert int(moved_priority["sort_order"]) == 5

    remove = client.post(
        "/admin/lookup/delete",
        data={"lookup_type": "doc_tag", "option_id": str(moved_priority["option_id"])},
        follow_redirects=False,
    )
    assert remove.status_code == 303

    active_rows = repo.list_lookup_options("doc_tag", active_only=True)
    assert "priority_review" not in active_rows["option_code"].tolist()
    assert active_rows["sort_order"].tolist() == list(range(1, len(active_rows) + 1))


def test_admin_ownership_reassignment_all_default_updates_vendor_offering_and_project(
    client: TestClient,
    isolated_local_db: Path,
) -> None:
    repo = get_repo()
    source_owner = "owner@example.com"
    replacement_owner = "pm@example.com"

    vendor_owner_id = repo.add_vendor_owner(
        vendor_id="vnd-001",
        owner_user_principal=source_owner,
        owner_role="business_owner",
        actor_user_principal="admin@example.com",
    )
    offerings = repo.get_vendor_offerings("vnd-001")
    assert not offerings.empty
    offering_id = str(offerings.iloc[0]["offering_id"])
    offering_owner_id = repo.add_offering_owner(
        vendor_id="vnd-001",
        offering_id=offering_id,
        owner_user_principal=source_owner,
        owner_role="business_owner",
        actor_user_principal="admin@example.com",
    )
    project_id = repo.create_project(
        vendor_id="vnd-001",
        actor_user_principal="admin@example.com",
        project_name="Ownership Reassign All",
        owner_principal=source_owner,
    )

    ownership_page = client.get("/admin?section=ownership&source_owner=owner%40example.com")
    assert ownership_page.status_code == 200
    assert "Ownership Reassignment" in ownership_page.text

    submit = client.post(
        "/admin/ownership/reassign",
        data={
            "source_owner": source_owner,
            "action_mode": "all_default",
            "default_target_owner": replacement_owner,
        },
        follow_redirects=False,
    )
    assert submit.status_code == 303

    reassigned_rows = repo.list_owner_reassignment_assignments(replacement_owner)
    reassigned_keys = {
        f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}"
        for row in reassigned_rows
    }
    assert f"vendor_owner::{vendor_owner_id}" in reassigned_keys
    assert f"offering_owner::{offering_owner_id}" in reassigned_keys
    assert f"project_owner::{project_id}" in reassigned_keys

    source_rows = repo.list_owner_reassignment_assignments(source_owner)
    source_keys = {
        f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}"
        for row in source_rows
    }
    assert f"vendor_owner::{vendor_owner_id}" not in source_keys
    assert f"offering_owner::{offering_owner_id}" not in source_keys
    assert f"project_owner::{project_id}" not in source_keys

    replacement_ref = repo.resolve_user_id(replacement_owner, allow_create=False) or replacement_owner
    with sqlite3.connect(str(isolated_local_db)) as conn:
        vendor_assignment = conn.execute(
            "SELECT user_principal, active_flag FROM vendor_owner_assignment WHERE assignment_id = ?",
            (vendor_owner_id,),
        ).fetchone()
        offering_assignment = conn.execute(
            "SELECT user_principal, active_flag FROM offering_owner_assignment WHERE assignment_id = ?",
            (offering_owner_id,),
        ).fetchone()
        assert vendor_assignment is not None
        assert offering_assignment is not None
        assert str(vendor_assignment[0]) == str(replacement_ref)
        assert str(offering_assignment[0]) == str(replacement_ref)
        assert int(vendor_assignment[1] or 0) == 1
        assert int(offering_assignment[1] or 0) == 1


def test_admin_ownership_reassignment_selected_per_row_supports_different_targets(
    client: TestClient,
    isolated_local_db: Path,
) -> None:
    repo = get_repo()
    source_owner = "owner@example.com"

    vendor_owner_id = repo.add_vendor_owner(
        vendor_id="vnd-001",
        owner_user_principal=source_owner,
        owner_role="business_owner",
        actor_user_principal="admin@example.com",
    )
    offerings = repo.get_vendor_offerings("vnd-001")
    assert not offerings.empty
    offering_id = str(offerings.iloc[0]["offering_id"])
    offering_owner_id = repo.add_offering_owner(
        vendor_id="vnd-001",
        offering_id=offering_id,
        owner_user_principal=source_owner,
        owner_role="business_owner",
        actor_user_principal="admin@example.com",
    )

    candidate_rows = repo.list_owner_reassignment_assignments(source_owner)
    key_vendor = f"vendor_owner::{vendor_owner_id}"
    key_offering = f"offering_owner::{offering_owner_id}"
    candidate_keys = {
        f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}"
        for row in candidate_rows
    }
    assert key_vendor in candidate_keys
    assert key_offering in candidate_keys

    submit = client.post(
        "/admin/ownership/reassign",
        data={
            "source_owner": source_owner,
            "action_mode": "selected_per_row",
            "selected_assignment_key": [key_vendor, key_offering],
            f"target_for__{key_vendor}": "pm@example.com",
            f"target_for__{key_offering}": "admin@example.com",
        },
        follow_redirects=False,
    )
    assert submit.status_code == 303

    pm_rows = repo.list_owner_reassignment_assignments("pm@example.com")
    pm_keys = {
        f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}"
        for row in pm_rows
    }
    assert key_vendor in pm_keys

    admin_rows = repo.list_owner_reassignment_assignments("admin@example.com")
    admin_keys = {
        f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}"
        for row in admin_rows
    }
    assert key_offering in admin_keys

    pm_ref = repo.resolve_user_id("pm@example.com", allow_create=False) or "pm@example.com"
    admin_ref = repo.resolve_user_id("admin@example.com", allow_create=False) or "admin@example.com"
    with sqlite3.connect(str(isolated_local_db)) as conn:
        vendor_assignment = conn.execute(
            "SELECT user_principal FROM vendor_owner_assignment WHERE assignment_id = ?",
            (vendor_owner_id,),
        ).fetchone()
        offering_assignment = conn.execute(
            "SELECT user_principal FROM offering_owner_assignment WHERE assignment_id = ?",
            (offering_owner_id,),
        ).fetchone()
        assert vendor_assignment is not None
        assert offering_assignment is not None
        assert str(vendor_assignment[0]) == str(pm_ref)
        assert str(offering_assignment[0]) == str(admin_ref)


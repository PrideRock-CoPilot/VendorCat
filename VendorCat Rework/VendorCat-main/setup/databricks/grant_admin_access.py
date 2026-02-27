#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass

from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class BootstrapInputs:
    profile: str
    host: str
    warehouse_id: str
    catalog: str
    schema: str
    login_identifier: str
    email: str
    network_id: str
    first_name: str
    last_name: str
    display_name: str
    employee_id: str
    granted_by: str


def _normalize_host(raw_host: str) -> str:
    value = str(raw_host or "").strip()
    if not value:
        return ""
    value = value.replace("https://", "").replace("http://", "").rstrip("/")
    return value


def _validate_identifier(value: str, label: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or not IDENTIFIER_PATTERN.fullmatch(cleaned):
        raise ValueError(f"{label} must match [A-Za-z0-9_]+ and cannot be empty.")
    return cleaned


def _split_display_name(display_name: str) -> tuple[str, str]:
    parts = [part for part in str(display_name or "").strip().split(" ") if part]
    if not parts:
        return "Admin", "User"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], " ".join(parts[1:])


def _build_inputs(args: argparse.Namespace) -> BootstrapInputs:
    cfg = Config(profile=args.profile)
    host = _normalize_host(args.host or cfg.host)
    if not host:
        raise RuntimeError("Unable to resolve Databricks host. Provide --host or configure host in profile.")

    me_user_name = ""
    me_display_name = ""
    try:
        workspace = WorkspaceClient(config=cfg)
        me = workspace.current_user.me()
        me_user_name = str(me.user_name or "").strip()
        me_display_name = str(me.display_name or "").strip()
    except Exception:
        me_user_name = ""
        me_display_name = ""

    login_identifier = str(args.login or me_user_name or "").strip().lower()
    if not login_identifier:
        raise RuntimeError(
            "Unable to resolve current user login from SDK profile lookup. Provide --login explicitly."
        )

    email = str(args.email or login_identifier).strip().lower()
    raw_display_name = str(args.display_name or me_display_name or "").strip()
    if not raw_display_name:
        raw_display_name = login_identifier.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    first_name, last_name = _split_display_name(raw_display_name)

    network_id = str(args.network_id or login_identifier.split("@", 1)[0]).strip().lower()
    employee_id = str(args.employee_id or f"BOOTSTRAP-{network_id.upper()}").strip()
    warehouse_id = str(args.warehouse_id or "").strip()
    if not warehouse_id:
        raise RuntimeError("--warehouse-id is required.")

    catalog = _validate_identifier(args.catalog, "catalog")
    schema = _validate_identifier(args.schema, "schema")
    granted_by = str(args.granted_by or login_identifier).strip().lower()

    return BootstrapInputs(
        profile=args.profile,
        host=host,
        warehouse_id=warehouse_id,
        catalog=catalog,
        schema=schema,
        login_identifier=login_identifier,
        email=email,
        network_id=network_id,
        first_name=first_name,
        last_name=last_name,
        display_name=raw_display_name,
        employee_id=employee_id,
        granted_by=granted_by,
    )


def _connect(inputs: BootstrapInputs):
    try:
        token = _access_token_from_cli(inputs.profile, inputs.host)
        return dbsql.connect(
            server_hostname=inputs.host,
            http_path=f"/sql/1.0/warehouses/{inputs.warehouse_id}",
            access_token=token,
        )
    except Exception:
        cfg = Config(profile=inputs.profile, host=f"https://{inputs.host}")

        def _credentials_provider():
            return cfg.authenticate

        return dbsql.connect(
            server_hostname=inputs.host,
            http_path=f"/sql/1.0/warehouses/{inputs.warehouse_id}",
            credentials_provider=_credentials_provider,
        )


def _access_token_from_cli(profile: str, host: str) -> str:
    result = subprocess.run(
        [
            "databricks",
            "auth",
            "token",
            "--profile",
            profile,
            "--host",
            f"https://{host}",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Failed to resolve CLI auth token.")
    payload = json.loads(result.stdout)
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("CLI token output did not contain access_token.")
    return token


def _table(inputs: BootstrapInputs, table_name: str) -> str:
    return f"`{inputs.catalog}`.`{inputs.schema}`.{table_name}"


def _upsert_admin_access(connection, inputs: BootstrapInputs) -> str:
    role_table = _table(inputs, "sec_role_definition")
    user_table = _table(inputs, "app_user_directory")
    employee_table = _table(inputs, "app_employee_directory")
    role_map_table = _table(inputs, "sec_user_role_map")
    user_id = f"usr-{uuid.uuid5(uuid.NAMESPACE_DNS, inputs.login_identifier).hex[:12]}"

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {role_table}
            SET active_flag = true,
                role_name = 'Admin',
                description = 'Bootstrap administrator role',
                approval_level = 3,
                can_edit = true,
                can_report = true,
                can_direct_apply = true,
                updated_at = current_timestamp(),
                updated_by = ?
            WHERE role_code = 'vendor_admin'
            """,
            [inputs.granted_by],
        )
        cursor.execute(
            f"""
            INSERT INTO {role_table}
              (role_code, role_name, description, approval_level, can_edit, can_report, can_direct_apply, active_flag, updated_at, updated_by)
            SELECT
                            'vendor_admin', 'Admin', 'Bootstrap administrator role', 3, true, true, true, true, current_timestamp(), ?
            WHERE NOT EXISTS (
              SELECT 1 FROM {role_table} WHERE role_code = 'vendor_admin'
            )
            """,
            [inputs.granted_by],
        )

        cursor.execute(
            f"""
            UPDATE {employee_table}
            SET email = ?,
                network_id = ?,
                employee_id = ?,
                first_name = ?,
                last_name = ?,
                display_name = ?,
                active_flag = 1
            WHERE lower(login_identifier) = lower(?)
            """,
            [
                inputs.email,
                inputs.network_id,
                inputs.employee_id,
                inputs.first_name,
                inputs.last_name,
                inputs.display_name,
                inputs.login_identifier,
            ],
        )
        cursor.execute(
            f"""
            INSERT INTO {employee_table}
              (login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag)
            SELECT ?, ?, ?, ?, null, ?, ?, ?, 1
            WHERE NOT EXISTS (
              SELECT 1 FROM {employee_table} WHERE lower(login_identifier) = lower(?)
            )
            """,
            [
                inputs.login_identifier,
                inputs.email,
                inputs.network_id,
                inputs.employee_id,
                inputs.first_name,
                inputs.last_name,
                inputs.display_name,
                inputs.login_identifier,
            ],
        )

        cursor.execute(
            f"""
            UPDATE {user_table}
            SET email = ?,
                network_id = ?,
                employee_id = ?,
                first_name = ?,
                last_name = ?,
                display_name = ?,
                active_flag = true,
                updated_at = current_timestamp(),
                last_seen_at = current_timestamp()
            WHERE lower(login_identifier) = lower(?)
            """,
            [
                inputs.email,
                inputs.network_id,
                inputs.employee_id,
                inputs.first_name,
                inputs.last_name,
                inputs.display_name,
                inputs.login_identifier,
            ],
        )
        cursor.execute(
            f"""
            INSERT INTO {user_table}
              (user_id, login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag, created_at, updated_at, last_seen_at)
            SELECT ?, ?, ?, ?, ?, null, ?, ?, ?, true, current_timestamp(), current_timestamp(), current_timestamp()
            WHERE NOT EXISTS (
              SELECT 1 FROM {user_table} WHERE lower(login_identifier) = lower(?)
            )
            """,
            [
                user_id,
                inputs.login_identifier,
                inputs.email,
                inputs.network_id,
                inputs.employee_id,
                inputs.first_name,
                inputs.last_name,
                inputs.display_name,
                inputs.login_identifier,
            ],
        )

        cursor.execute(
            f"""
            SELECT user_id
            FROM {user_table}
            WHERE lower(login_identifier) = lower(?)
            LIMIT 1
            """,
            [inputs.login_identifier],
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            raise RuntimeError("Unable to resolve user_id after upsert.")
        resolved_user_id = str(row[0]).strip()

        cursor.execute(
            f"""
            UPDATE {role_map_table}
            SET active_flag = true,
                revoked_at = null,
                granted_by = ?,
                granted_at = current_timestamp()
            WHERE user_principal = ?
              AND role_code = 'vendor_admin'
            """,
            [inputs.granted_by, resolved_user_id],
        )
        cursor.execute(
            f"""
            INSERT INTO {role_map_table}
              (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
            SELECT ?, 'vendor_admin', true, ?, current_timestamp(), null
            WHERE NOT EXISTS (
              SELECT 1
              FROM {role_map_table}
              WHERE user_principal = ?
                AND role_code = 'vendor_admin'
                AND active_flag = true
                AND revoked_at IS NULL
            )
            """,
            [resolved_user_id, inputs.granted_by, resolved_user_id],
        )

        return resolved_user_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grant vendor_admin access to the current Databricks account.")
    parser.add_argument("--profile", default="sso", help="Databricks CLI profile name.")
    parser.add_argument("--host", default="", help="Optional Databricks host override.")
    parser.add_argument("--warehouse-id", default="955428814f623a0e", help="SQL warehouse id.")
    parser.add_argument("--catalog", default="a1_dlk", help="Target catalog.")
    parser.add_argument("--schema", default="twvendor", help="Target schema.")
    parser.add_argument("--login", default="", help="User principal to grant (defaults to current account).")
    parser.add_argument("--email", default="", help="Optional email override.")
    parser.add_argument("--display-name", default="", help="Optional display name override.")
    parser.add_argument("--network-id", default="", help="Optional network id override.")
    parser.add_argument("--employee-id", default="", help="Optional employee id override.")
    parser.add_argument("--granted-by", default="", help="Actor recorded in audit fields.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inputs = _build_inputs(args)
        connection = _connect(inputs)
        try:
            resolved_user_id = _upsert_admin_access(connection, inputs)
        finally:
            connection.close()

        print("✅ Admin bootstrap completed")
        print(f"   profile: {inputs.profile}")
        print(f"   host: {inputs.host}")
        print(f"   warehouse: {inputs.warehouse_id}")
        print(f"   principal: {inputs.login_identifier}")
        print(f"   user_id: {resolved_user_id}")
        print("   role: vendor_admin")
        return 0
    except Exception as exc:
        print(f"❌ Failed to grant admin access: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

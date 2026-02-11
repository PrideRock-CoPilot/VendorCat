from __future__ import annotations

import argparse
import re
import sys


REQUIRED_TABLES = (
    "core_vendor",
    "sec_user_role_map",
    "app_user_settings",
    "app_user_directory",
    "app_lookup_option",
)

REQUIRED_COLUMN_MAP = {
    "core_vendor_offering": ("lob", "service_type"),
    "app_lookup_option": ("valid_from_ts", "valid_to_ts", "is_current", "deleted_flag"),
}


def _parse_fq_schema(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    parts = [item.strip() for item in raw.split(".", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Expected --fq-schema in '<catalog>.<schema>' format.")
    return parts[0], parts[1]


def _quote_ident(value: str) -> str:
    return f"`{str(value).replace('`', '``')}`"


def _table_ref(catalog: str, schema: str, table: str) -> str:
    return f"{_quote_ident(catalog)}.{_quote_ident(schema)}.{_quote_ident(table)}"


def _string_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _current_user(spark) -> str:
    row = spark.sql("SELECT current_user() AS principal").first()
    principal = str((row["principal"] if row else "") or "").strip()
    if not principal:
        raise RuntimeError("Could not resolve current_user() from Databricks session.")
    return principal


def _principal_to_display_name(user_principal: str) -> str:
    raw = str(user_principal or "").strip()
    if not raw:
        return "Unknown User"
    normalized = raw.split("\\")[-1].split("/")[-1]
    if "@" in normalized:
        normalized = normalized.split("@", 1)[0]
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    normalized = re.sub(r"[._-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return "Unknown User"
    parts = [part.capitalize() for part in normalized.split(" ") if part]
    if not parts:
        return "Unknown User"
    if len(parts) == 1:
        return f"{parts[0]} User"
    return " ".join(parts)


def _derive_identity(principal: str) -> dict[str, str | None]:
    login_identifier = str(principal or "").strip()
    email = login_identifier if "@" in login_identifier else None
    network_id = None
    if not email and ("\\" in login_identifier or "/" in login_identifier):
        network_id = login_identifier.split("\\")[-1].split("/")[-1]
    display_name = _principal_to_display_name(login_identifier)
    parts = [part for part in display_name.split(" ") if part and part.lower() != "user"]
    first_name = parts[0] if parts else None
    last_name = " ".join(parts[1:]) if len(parts) > 1 else None
    return {
        "login_identifier": login_identifier,
        "email": email,
        "network_id": network_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
    }


def _validate_required_tables(spark, *, catalog: str, schema: str) -> None:
    info_schema_ref = f"{_quote_ident(catalog)}.information_schema.tables"
    required = ", ".join(_string_literal(name) for name in REQUIRED_TABLES)
    query = (
        f"SELECT table_name FROM {info_schema_ref} "
        f"WHERE table_schema = {_string_literal(schema)} AND table_name IN ({required})"
    )
    rows = spark.sql(query).collect()
    found = {str(row["table_name"]).strip().lower() for row in rows}
    missing = [name for name in REQUIRED_TABLES if name.lower() not in found]
    if missing:
        raise RuntimeError(
            f"Missing required tables in {catalog}.{schema}: {', '.join(missing)}"
        )


def _validate_required_columns(spark, *, catalog: str, schema: str) -> None:
    info_schema_ref = f"{_quote_ident(catalog)}.information_schema.columns"
    missing: list[str] = []
    for table_name, required_columns in REQUIRED_COLUMN_MAP.items():
        required = ", ".join(_string_literal(name) for name in required_columns)
        query = (
            f"SELECT column_name FROM {info_schema_ref} "
            f"WHERE table_schema = {_string_literal(schema)} "
            f"AND table_name = {_string_literal(table_name)} "
            f"AND column_name IN ({required})"
        )
        rows = spark.sql(query).collect()
        found = {str(row["column_name"]).strip().lower() for row in rows}
        for column_name in required_columns:
            if column_name.lower() not in found:
                missing.append(f"{table_name}.{column_name}")
    if missing:
        raise RuntimeError(
            f"Missing required columns in {catalog}.{schema}: {', '.join(missing)}"
        )


def _validate_select_access(spark, *, catalog: str, schema: str) -> None:
    inaccessible: list[str] = []
    probes = list(REQUIRED_TABLES) + list(REQUIRED_COLUMN_MAP.keys())
    for table_name in probes:
        table = _table_ref(catalog, schema, table_name)
        try:
            spark.sql(f"SELECT * FROM {table} LIMIT 1").collect()
        except Exception as exc:
            inaccessible.append(f"{table_name} ({exc})")
    if inaccessible:
        raise RuntimeError(
            "Schema objects exist but are not accessible: " + "; ".join(inaccessible)
        )


def _upsert_user_directory(spark, *, catalog: str, schema: str, identity: dict[str, str | None]) -> None:
    table = _table_ref(catalog, schema, "app_user_directory")
    source_view = "_tmp_vc_bootstrap_user"
    source_row = {
        "login_identifier": str(identity["login_identifier"] or "").strip(),
        "email": identity.get("email"),
        "network_id": identity.get("network_id"),
        "first_name": identity.get("first_name"),
        "last_name": identity.get("last_name"),
        "display_name": str(identity["display_name"] or "Unknown User").strip(),
    }
    source_df = spark.createDataFrame([source_row])
    source_df.createOrReplaceTempView(source_view)
    spark.sql(
        f"""
MERGE INTO {table} target
USING {source_view} source
ON lower(target.login_identifier) = lower(source.login_identifier)
WHEN MATCHED THEN
  UPDATE SET
    target.email = source.email,
    target.network_id = source.network_id,
    target.first_name = source.first_name,
    target.last_name = source.last_name,
    target.display_name = source.display_name,
    target.active_flag = true,
    target.updated_at = current_timestamp(),
    target.last_seen_at = current_timestamp()
WHEN NOT MATCHED THEN
  INSERT (
    user_id,
    login_identifier,
    email,
    network_id,
    first_name,
    last_name,
    display_name,
    active_flag,
    created_at,
    updated_at,
    last_seen_at
  )
  VALUES (
    concat('usr-', substr(replace(uuid(), '-', ''), 1, 20)),
    source.login_identifier,
    source.email,
    source.network_id,
    source.first_name,
    source.last_name,
    source.display_name,
    true,
    current_timestamp(),
    current_timestamp(),
    current_timestamp()
  )
"""
    )


def _upsert_role_grants(
    spark,
    *,
    catalog: str,
    schema: str,
    user_principal: str,
    granted_by: str,
    roles: list[str],
) -> None:
    table = _table_ref(catalog, schema, "sec_user_role_map")
    source_view = "_tmp_vc_bootstrap_roles"
    source_rows = [
        {
            "user_principal": user_principal,
            "role_code": role,
            "granted_by": granted_by,
        }
        for role in roles
    ]
    source_df = spark.createDataFrame(source_rows)
    source_df.createOrReplaceTempView(source_view)
    spark.sql(
        f"""
MERGE INTO {table} target
USING {source_view} source
ON lower(target.user_principal) = lower(source.user_principal)
AND lower(target.role_code) = lower(source.role_code)
WHEN MATCHED THEN
  UPDATE SET
    target.active_flag = true,
    target.granted_by = source.granted_by,
    target.granted_at = current_timestamp(),
    target.revoked_at = NULL
WHEN NOT MATCHED THEN
  INSERT (
    user_principal,
    role_code,
    active_flag,
    granted_by,
    granted_at,
    revoked_at
  )
  VALUES (
    source.user_principal,
    source.role_code,
    true,
    source.granted_by,
    current_timestamp(),
    NULL
  )
"""
    )


def _parse_roles(value: str) -> list[str]:
    roles = [
        str(token or "").strip().lower()
        for token in str(value or "").split(",")
        if str(token or "").strip()
    ]
    if not roles:
        raise ValueError("Provide at least one role via --roles.")
    return list(dict.fromkeys(roles))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Databricks Vendor Catalog schema access and bootstrap "
            "the running user as admin."
        )
    )
    parser.add_argument(
        "--fq-schema",
        required=True,
        help="Target '<catalog>.<schema>' (example: a1_dlk.twanalytics).",
    )
    parser.add_argument(
        "--principal",
        default="",
        help="User principal to bootstrap (defaults to Databricks current_user()).",
    )
    parser.add_argument(
        "--roles",
        default="vendor_admin",
        help="Comma-separated roles to grant (default: vendor_admin).",
    )
    parser.add_argument(
        "--granted-by",
        default="",
        help="Audit grant actor (defaults to principal).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; do not write user/role rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        from pyspark.sql import SparkSession  # type: ignore
    except Exception:
        print(
            "ERROR: pyspark is not available. Run this script inside Databricks.",
            file=sys.stderr,
        )
        return 2

    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()

    try:
        catalog, schema = _parse_fq_schema(args.fq_schema)
        _validate_required_tables(spark, catalog=catalog, schema=schema)
        _validate_required_columns(spark, catalog=catalog, schema=schema)
        _validate_select_access(spark, catalog=catalog, schema=schema)

        principal = str(args.principal or "").strip() or _current_user(spark)
        roles = _parse_roles(args.roles)
        granted_by = str(args.granted_by or "").strip() or principal
        identity = _derive_identity(principal)

        print(f"Schema validation passed for {catalog}.{schema}.")
        print(f"Bootstrap principal: {principal}")
        print(f"Roles to grant: {', '.join(roles)}")

        if args.dry_run:
            print("Dry run mode: no writes performed.")
            return 0

        _upsert_user_directory(spark, catalog=catalog, schema=schema, identity=identity)
        _upsert_role_grants(
            spark,
            catalog=catalog,
            schema=schema,
            user_principal=principal,
            granted_by=granted_by,
            roles=roles,
        )

        print(f"User directory and role grants bootstrapped for {principal}.")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

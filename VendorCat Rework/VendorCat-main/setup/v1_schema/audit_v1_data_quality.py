from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class AuditIssue:
    category: str
    severity: str
    check: str
    count: int
    sample: list[dict[str, Any]]


def _normalize_value(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    normalized_chars: list[str] = []
    previous_separator = False
    for char in text:
        if char.isalnum():
            normalized_chars.append(char)
            previous_separator = False
            continue
        if previous_separator:
            continue
        normalized_chars.append("_")
        previous_separator = True
    normalized = "".join(normalized_chars).strip("_")
    return normalized


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (str(table_name or "").strip(),),
    ).fetchone()
    return row is not None


def _query_rows(conn: sqlite3.Connection, statement: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor = conn.execute(statement, params)
    columns = [str(item[0]) for item in cursor.description or []]
    rows = cursor.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({columns[index]: row[index] for index in range(len(columns))})
    return out


def _run_issue_query(
    conn: sqlite3.Connection,
    *,
    category: str,
    severity: str,
    check: str,
    statement: str,
    params: tuple[Any, ...] = (),
    sample_limit: int = 20,
) -> AuditIssue:
    wrapped = f"SELECT * FROM ({statement}) AS audit_rows"
    try:
        count_row = conn.execute(f"SELECT COUNT(*) FROM ({statement}) AS audit_count", params).fetchone()
        total_count = int((count_row[0] if count_row else 0) or 0)
        sample = _query_rows(conn, f"{wrapped} LIMIT {int(sample_limit)}", params)
    except sqlite3.OperationalError:
        total_count = 0
        sample = []
    return AuditIssue(
        category=category,
        severity=severity,
        check=check,
        count=total_count,
        sample=sample,
    )


def _duplicate_key_issues(conn: sqlite3.Connection) -> list[AuditIssue]:
    checks: list[tuple[str, str, str, str]] = [
        (
            "core_vendor",
            "high",
            "duplicate_core_vendor_legal_name_casefold",
            """
            SELECT lower(trim(legal_name)) AS natural_key, COUNT(*) AS duplicate_count
            FROM core_vendor
            WHERE trim(coalesce(legal_name, '')) <> ''
            GROUP BY lower(trim(legal_name))
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, natural_key
            """,
        ),
        (
            "core_vendor_offering",
            "high",
            "duplicate_core_offering_name_per_vendor_casefold",
            """
            SELECT vendor_id, lower(trim(offering_name)) AS natural_key, COUNT(*) AS duplicate_count
            FROM core_vendor_offering
            WHERE trim(coalesce(vendor_id, '')) <> ''
              AND trim(coalesce(offering_name, '')) <> ''
            GROUP BY vendor_id, lower(trim(offering_name))
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, vendor_id, natural_key
            """,
        ),
        (
            "vendor",
            "high",
            "duplicate_canonical_vendor_legal_name_casefold",
            """
            SELECT lower(trim(legal_name)) AS natural_key, COUNT(*) AS duplicate_count
            FROM vendor
            WHERE trim(coalesce(legal_name, '')) <> ''
            GROUP BY lower(trim(legal_name))
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, natural_key
            """,
        ),
        (
            "offering",
            "high",
            "duplicate_canonical_offering_name_per_vendor_casefold",
            """
            SELECT vendor_id, lower(trim(offering_name)) AS natural_key, COUNT(*) AS duplicate_count
            FROM offering
            WHERE trim(coalesce(vendor_id, '')) <> ''
              AND trim(coalesce(offering_name, '')) <> ''
            GROUP BY vendor_id, lower(trim(offering_name))
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, vendor_id, natural_key
            """,
        ),
    ]
    issues: list[AuditIssue] = []
    for table_name, severity, check_name, statement in checks:
        if not _table_exists(conn, table_name):
            continue
        issues.append(
            _run_issue_query(
                conn,
                category="duplicate_natural_keys",
                severity=severity,
                check=check_name,
                statement=statement,
            )
        )
    return issues


def _orphan_reference_issues(conn: sqlite3.Connection) -> list[AuditIssue]:
    checks: list[tuple[list[str], str, str, str]] = [
        (
            ["core_vendor_offering", "core_vendor"],
            "high",
            "orphan_core_offering_vendor_id",
            """
            SELECT o.offering_id, o.vendor_id
            FROM core_vendor_offering o
            LEFT JOIN core_vendor v ON v.vendor_id = o.vendor_id
            WHERE trim(coalesce(o.vendor_id, '')) <> ''
              AND v.vendor_id IS NULL
            """,
        ),
        (
            ["core_offering_contact", "core_vendor_offering"],
            "high",
            "orphan_core_offering_contact",
            """
            SELECT c.offering_contact_id, c.offering_id
            FROM core_offering_contact c
            LEFT JOIN core_vendor_offering o ON o.offering_id = c.offering_id
            WHERE trim(coalesce(c.offering_id, '')) <> ''
              AND o.offering_id IS NULL
            """,
        ),
        (
            ["core_vendor_contact", "core_vendor"],
            "high",
            "orphan_core_vendor_contact",
            """
            SELECT c.vendor_contact_id, c.vendor_id
            FROM core_vendor_contact c
            LEFT JOIN core_vendor v ON v.vendor_id = c.vendor_id
            WHERE trim(coalesce(c.vendor_id, '')) <> ''
              AND v.vendor_id IS NULL
            """,
        ),
        (
            ["core_contract", "core_vendor"],
            "high",
            "orphan_core_contract_vendor",
            """
            SELECT c.contract_id, c.vendor_id
            FROM core_contract c
            LEFT JOIN core_vendor v ON v.vendor_id = c.vendor_id
            WHERE trim(coalesce(c.vendor_id, '')) <> ''
              AND v.vendor_id IS NULL
            """,
        ),
        (
            ["core_contract", "core_vendor_offering"],
            "high",
            "orphan_core_contract_offering",
            """
            SELECT c.contract_id, c.offering_id
            FROM core_contract c
            LEFT JOIN core_vendor_offering o ON o.offering_id = c.offering_id
            WHERE trim(coalesce(c.offering_id, '')) <> ''
              AND o.offering_id IS NULL
            """,
        ),
        (
            ["offering", "vendor"],
            "high",
            "orphan_canonical_offering_vendor",
            """
            SELECT o.offering_id, o.vendor_id
            FROM offering o
            LEFT JOIN vendor v ON v.vendor_id = o.vendor_id
            WHERE trim(coalesce(o.vendor_id, '')) <> ''
              AND v.vendor_id IS NULL
            """,
        ),
        (
            ["vendor_business_unit_assignment", "vendor"],
            "high",
            "orphan_vendor_business_unit_assignment_vendor",
            """
            SELECT a.assignment_id, a.vendor_id
            FROM vendor_business_unit_assignment a
            LEFT JOIN vendor v ON v.vendor_id = a.vendor_id
            WHERE trim(coalesce(a.vendor_id, '')) <> ''
              AND v.vendor_id IS NULL
            """,
        ),
        (
            ["vendor_business_unit_assignment", "lkp_business_unit"],
            "high",
            "orphan_vendor_business_unit_assignment_lookup",
            """
            SELECT a.assignment_id, a.business_unit_id
            FROM vendor_business_unit_assignment a
            LEFT JOIN lkp_business_unit b ON b.business_unit_id = a.business_unit_id
            WHERE trim(coalesce(a.business_unit_id, '')) <> ''
              AND b.business_unit_id IS NULL
            """,
        ),
        (
            ["offering_business_unit_assignment", "offering"],
            "high",
            "orphan_offering_business_unit_assignment_offering",
            """
            SELECT a.assignment_id, a.offering_id
            FROM offering_business_unit_assignment a
            LEFT JOIN offering o ON o.offering_id = a.offering_id
            WHERE trim(coalesce(a.offering_id, '')) <> ''
              AND o.offering_id IS NULL
            """,
        ),
        (
            ["offering_business_unit_assignment", "lkp_business_unit"],
            "high",
            "orphan_offering_business_unit_assignment_lookup",
            """
            SELECT a.assignment_id, a.business_unit_id
            FROM offering_business_unit_assignment a
            LEFT JOIN lkp_business_unit b ON b.business_unit_id = a.business_unit_id
            WHERE trim(coalesce(a.business_unit_id, '')) <> ''
              AND b.business_unit_id IS NULL
            """,
        ),
    ]
    issues: list[AuditIssue] = []
    for required_tables, severity, check_name, statement in checks:
        if any(not _table_exists(conn, table_name) for table_name in required_tables):
            continue
        issues.append(
            _run_issue_query(
                conn,
                category="orphan_references",
                severity=severity,
                check=check_name,
                statement=statement,
            )
        )
    return issues


def _one_to_many_compression_issues(conn: sqlite3.Connection) -> list[AuditIssue]:
    checks: list[tuple[list[str], str, str, str]] = [
        (
            ["core_vendor", "core_vendor_org_assignment"],
            "medium",
            "core_vendor_single_owner_org_with_multiple_active_assignments",
            """
            SELECT
              v.vendor_id,
              v.owner_org_id,
              COUNT(DISTINCT a.org_id) AS active_business_unit_count
            FROM core_vendor v
            JOIN core_vendor_org_assignment a ON a.vendor_id = v.vendor_id
            WHERE coalesce(a.active_flag, 1) IN (1, '1', 'true', 'TRUE')
              AND trim(coalesce(a.org_id, '')) <> ''
            GROUP BY v.vendor_id, v.owner_org_id
            HAVING COUNT(DISTINCT a.org_id) > 1
            ORDER BY active_business_unit_count DESC, v.vendor_id
            """,
        ),
        (
            ["vendor_business_unit_assignment"],
            "medium",
            "duplicate_active_vendor_business_unit_assignments",
            """
            SELECT vendor_id, business_unit_id, COUNT(*) AS duplicate_count
            FROM vendor_business_unit_assignment
            WHERE coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE')
            GROUP BY vendor_id, business_unit_id
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, vendor_id, business_unit_id
            """,
        ),
        (
            ["offering_business_unit_assignment"],
            "medium",
            "duplicate_active_offering_business_unit_assignments",
            """
            SELECT offering_id, business_unit_id, COUNT(*) AS duplicate_count
            FROM offering_business_unit_assignment
            WHERE coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE')
            GROUP BY offering_id, business_unit_id
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, offering_id, business_unit_id
            """,
        ),
    ]
    issues: list[AuditIssue] = []
    for required_tables, severity, check_name, statement in checks:
        if any(not _table_exists(conn, table_name) for table_name in required_tables):
            continue
        issues.append(
            _run_issue_query(
                conn,
                category="one_to_many_compression",
                severity=severity,
                check=check_name,
                statement=statement,
            )
        )
    return issues


def _lookup_value_drift_issues(conn: sqlite3.Connection) -> list[AuditIssue]:
    if not _table_exists(conn, "app_lookup_option"):
        return []

    lookup_rows = _query_rows(
        conn,
        """
        SELECT lookup_type, option_code, option_label
        FROM app_lookup_option
        WHERE coalesce(is_current, 1) IN (1, '1', 'true', 'TRUE')
          AND coalesce(deleted_flag, 0) IN (0, '0', 'false', 'FALSE')
          AND coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE')
        """,
    )
    lookup_values: dict[str, set[str]] = {}
    for row in lookup_rows:
        lookup_type = str(row.get("lookup_type") or "").strip().lower()
        if not lookup_type:
            continue
        bucket = lookup_values.setdefault(lookup_type, set())
        code = _normalize_value(row.get("option_code"))
        label = _normalize_value(row.get("option_label"))
        if code:
            bucket.add(code)
        if label:
            bucket.add(label)

    governed_fields: list[tuple[str, str, str, str]] = [
        ("core_vendor", "owner_org_id", "owner_organization", "high"),
        ("core_vendor", "lifecycle_state", "lifecycle_state", "high"),
        ("core_vendor", "risk_tier", "risk_tier", "high"),
        ("core_vendor_offering", "business_unit", "offering_business_unit", "high"),
        ("core_vendor_offering", "service_type", "offering_service_type", "high"),
        ("core_vendor_offering", "offering_type", "offering_type", "high"),
        ("core_vendor_offering", "lifecycle_state", "lifecycle_state", "high"),
        ("core_vendor_contact", "contact_type", "contact_type", "medium"),
        ("core_offering_contact", "contact_type", "contact_type", "medium"),
        ("core_vendor_business_owner", "owner_role", "owner_role", "medium"),
        ("core_offering_business_owner", "owner_role", "owner_role", "medium"),
    ]

    issues: list[AuditIssue] = []
    for table_name, column_name, lookup_type, severity in governed_fields:
        if not _table_exists(conn, table_name):
            continue
        allowed = set(lookup_values.get(lookup_type, set()))
        if not allowed:
            continue
        distinct_rows = _query_rows(
            conn,
            (
                f"SELECT {column_name} AS field_value, COUNT(*) AS row_count "
                f"FROM {table_name} "
                f"WHERE trim(coalesce({column_name}, '')) <> '' "
                f"GROUP BY {column_name} ORDER BY row_count DESC"
            ),
        )
        unknown_rows: list[dict[str, Any]] = []
        total_unknown_count = 0
        for row in distinct_rows:
            raw_value = str(row.get("field_value") or "").strip()
            normalized = _normalize_value(raw_value)
            if not normalized or normalized in allowed:
                continue
            row_count = int(row.get("row_count") or 0)
            total_unknown_count += row_count
            unknown_rows.append(
                {
                    "table_name": table_name,
                    "column_name": column_name,
                    "lookup_type": lookup_type,
                    "field_value": raw_value,
                    "row_count": row_count,
                }
            )
        issues.append(
            AuditIssue(
                category="lookup_drift",
                severity=severity,
                check=f"unmanaged_{table_name}_{column_name}",
                count=total_unknown_count,
                sample=unknown_rows[:20],
            )
        )
    return issues


def _required_value_issues(conn: sqlite3.Connection) -> list[AuditIssue]:
    checks: list[tuple[str, str, str, str]] = [
        ("core_vendor", "vendor_id", "high", "core_vendor_missing_vendor_id"),
        ("core_vendor", "legal_name", "high", "core_vendor_missing_legal_name"),
        ("core_vendor", "lifecycle_state", "high", "core_vendor_missing_lifecycle_state"),
        ("core_vendor", "owner_org_id", "high", "core_vendor_missing_owner_org_id"),
        ("core_vendor_offering", "offering_id", "high", "core_offering_missing_offering_id"),
        ("core_vendor_offering", "vendor_id", "high", "core_offering_missing_vendor_id"),
        ("core_vendor_offering", "offering_name", "high", "core_offering_missing_offering_name"),
        ("core_vendor_offering", "lifecycle_state", "high", "core_offering_missing_lifecycle_state"),
        ("vendor", "vendor_id", "high", "canonical_vendor_missing_vendor_id"),
        ("vendor", "legal_name", "high", "canonical_vendor_missing_legal_name"),
        ("offering", "offering_id", "high", "canonical_offering_missing_offering_id"),
        ("offering", "vendor_id", "high", "canonical_offering_missing_vendor_id"),
        ("offering", "offering_name", "high", "canonical_offering_missing_offering_name"),
    ]
    issues: list[AuditIssue] = []
    for table_name, column_name, severity, check_name in checks:
        if not _table_exists(conn, table_name):
            continue
        statement = (
            f"SELECT rowid AS row_ref, {column_name} AS field_value "
            f"FROM {table_name} "
            f"WHERE {column_name} IS NULL OR trim(cast({column_name} AS TEXT)) = ''"
        )
        issues.append(
            _run_issue_query(
                conn,
                category="required_value_violations",
                severity=severity,
                check=check_name,
                statement=statement,
            )
        )
    return issues


def _reconciliation_metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    metrics: dict[str, Any] = {}

    def count_if_exists(table_name: str, where_clause: str = "") -> int | None:
        if not _table_exists(conn, table_name):
            return None
        sql = f"SELECT COUNT(*) FROM {table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        try:
            row = conn.execute(sql).fetchone()
        except sqlite3.OperationalError:
            return None
        return int((row[0] if row else 0) or 0)

    metrics["core_vendor_count"] = count_if_exists("core_vendor")
    metrics["canonical_vendor_count"] = count_if_exists("vendor")
    metrics["core_offering_count"] = count_if_exists("core_vendor_offering")
    metrics["canonical_offering_count"] = count_if_exists("offering")
    metrics["core_active_vendor_org_assignment_count"] = count_if_exists(
        "core_vendor_org_assignment",
        "coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE')",
    )
    metrics["canonical_active_vendor_business_unit_assignment_count"] = count_if_exists(
        "vendor_business_unit_assignment",
        "coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE')",
    )
    metrics["core_nonblank_offering_business_unit_count"] = count_if_exists(
        "core_vendor_offering",
        "trim(coalesce(business_unit, '')) <> ''",
    )
    metrics["canonical_active_offering_business_unit_assignment_count"] = count_if_exists(
        "offering_business_unit_assignment",
        "coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE')",
    )

    if metrics["core_vendor_count"] is not None and metrics["canonical_vendor_count"] is not None:
        metrics["vendor_count_delta"] = int(metrics["canonical_vendor_count"] - metrics["core_vendor_count"])
    if metrics["core_offering_count"] is not None and metrics["canonical_offering_count"] is not None:
        metrics["offering_count_delta"] = int(metrics["canonical_offering_count"] - metrics["core_offering_count"])
    if (
        metrics["core_active_vendor_org_assignment_count"] is not None
        and metrics["canonical_active_vendor_business_unit_assignment_count"] is not None
    ):
        metrics["vendor_business_unit_assignment_delta"] = int(
            metrics["canonical_active_vendor_business_unit_assignment_count"]
            - metrics["core_active_vendor_org_assignment_count"]
        )
    if (
        metrics["core_nonblank_offering_business_unit_count"] is not None
        and metrics["canonical_active_offering_business_unit_assignment_count"] is not None
    ):
        metrics["offering_business_unit_assignment_delta"] = int(
            metrics["canonical_active_offering_business_unit_assignment_count"]
            - metrics["core_nonblank_offering_business_unit_count"]
        )

    return metrics


def _reconciliation_issues(metrics: dict[str, Any]) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    delta_checks = [
        ("vendor_count_delta", "reconciliation_vendor_count_delta"),
        ("offering_count_delta", "reconciliation_offering_count_delta"),
        ("vendor_business_unit_assignment_delta", "reconciliation_vendor_business_unit_assignment_delta"),
        ("offering_business_unit_assignment_delta", "reconciliation_offering_business_unit_assignment_delta"),
    ]
    for metric_key, check_name in delta_checks:
        if metric_key not in metrics:
            continue
        delta_value = int(metrics.get(metric_key) or 0)
        issues.append(
            AuditIssue(
                category="pre_post_reconciliation",
                severity="medium",
                check=check_name,
                count=abs(delta_value),
                sample=[{"metric": metric_key, "delta": delta_value}],
            )
        )
    return issues


def run_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        issues: list[AuditIssue] = []
        issues.extend(_duplicate_key_issues(conn))
        issues.extend(_orphan_reference_issues(conn))
        issues.extend(_one_to_many_compression_issues(conn))
        issues.extend(_lookup_value_drift_issues(conn))
        issues.extend(_required_value_issues(conn))
        metrics = _reconciliation_metrics(conn)
        issues.extend(_reconciliation_issues(metrics))

    issue_dicts = [asdict(issue) for issue in issues]
    open_issue_count = sum(1 for item in issue_dicts if int(item.get("count") or 0) > 0)
    high_issue_count = sum(
        1
        for item in issue_dicts
        if int(item.get("count") or 0) > 0 and str(item.get("severity") or "").lower() == "high"
    )
    medium_issue_count = sum(
        1
        for item in issue_dicts
        if int(item.get("count") or 0) > 0 and str(item.get("severity") or "").lower() == "medium"
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "database_path": str(db_path),
        "issue_count": len(issue_dicts),
        "open_issue_count": open_issue_count,
        "high_issue_count": high_issue_count,
        "medium_issue_count": medium_issue_count,
        "issues": issue_dicts,
        "metrics": metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run V1 data quality audit checks for duplicate keys, FK orphans, lookup drift, and reconciliation."
    )
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parents[1] / "local_db" / "twvendor_local_v1.db"),
        help="Path to SQLite database file.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write JSON audit output.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when any high or medium issues are present.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return 2

    report = run_audit(db_path)
    print("V1 data quality audit complete")
    print(f"- database: {report['database_path']}")
    print(f"- checks: {report['issue_count']}")
    print(f"- open issues: {report['open_issue_count']}")
    print(f"- high severity open issues: {report['high_issue_count']}")
    print(f"- medium severity open issues: {report['medium_issue_count']}")

    for issue in report["issues"]:
        count = int(issue.get("count") or 0)
        if count <= 0:
            continue
        print(
            f"  * [{issue.get('severity')}] {issue.get('check')}: {count}"
        )

    output_json = str(args.output_json or "").strip()
    if output_json:
        output_path = Path(output_json).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"- wrote report: {output_path}")

    if args.strict and (int(report.get("high_issue_count") or 0) > 0 or int(report.get("medium_issue_count") or 0) > 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

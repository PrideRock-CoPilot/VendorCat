# SQL Inventory

## Snapshot
- Runtime SQL files under `src/schema/canonical + src/schema/rendered`: 225

## Implications For Rebuild
- SQL remains first-class in rebuild architecture.
- Canonical schema definitions and adapters will live under `src/schema/` and `src/apps/core/sql/`.
- Existing SQL files are reference-only for parity extraction.


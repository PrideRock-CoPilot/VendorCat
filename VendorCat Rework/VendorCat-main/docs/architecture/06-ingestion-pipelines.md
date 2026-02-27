# Ingestion And Pipeline Design

## Source Systems
- PeopleSoft vendor and contract data.
- Zycus supplier and sourcing data.
- Approved spreadsheet feeds from controlled business teams.

## Ingestion Strategy
- Land all source payloads into immutable `src_` tables in `twvendor`.
- Capture batch metadata in `src_ingest_batch`.
- Preserve original payload and source keys for every row.

## Transformation Strategy
- Normalize and map source records into `core_` canonical tables.
- Apply dedupe and survivorship logic with deterministic rules.
- Write full history into `hist_` tables for changed entities.
- Write change evidence into `audit_` tables for every update.

## App Edit Strategy
- App reads from secure `rpt_` views.
- App writes through controlled request tables in `app_`.
- Approved requests apply updates to `core_` and append to `hist_` and `audit_`.
- Source-of-origin records in `src_` remain unchanged.

## Data Quality Rules
- Required fields for active vendors cannot be null.
- Vendor plus offering name combinations must be unique within active scope.
- Country and currency codes must be valid ISO values.
- Contract cancellation must include reason code and note.
- Demo non-selection must include reason code and note.

## Orchestration
- Lakeflow pipelines for ingest and conformance jobs.
- Lakeflow Jobs for dependency orchestration and retries.
- Dead-letter handling for malformed source rows.

## Reconciliation
- Batch-level row count and key-level comparison by source.
- Reject and quarantine invalid spreadsheet schemas.
- Publish reconciliation report per ingest batch.

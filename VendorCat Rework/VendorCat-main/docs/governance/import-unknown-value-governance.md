# Import Unknown Value Governance Specification

## Objective

Prevent unmanaged lookup values from entering runtime entities while preserving import throughput.

## Workflow

1. Parse inbound file into staging (`app_import_job`, `app_import_stage_row`, area rows).
2. Validate governed dimensions against active lookup options.
3. For unknown values, create `app_import_lookup_candidate` rows with status `pending`.
4. Block `/imports/apply` while any pending candidates exist for the job.
5. Steward reviews each candidate:
   - `approved`: optional auto-create lookup option, candidate marked approved.
   - `rejected`: candidate marked rejected with note.
6. Re-run apply after pending count reaches zero.

## Candidate Record Requirements

| Field | Purpose |
|---|---|
| `import_job_id` | Trace candidate to staging job |
| `area_key` | Indicates vendor/offering/contact context |
| `row_index` | Trace to exact source row |
| `lookup_type` | Domain being validated |
| `option_code` | Normalized candidate code |
| `option_label` | Source label/value |
| `status` | `pending`, `approved`, `rejected` |
| `review_note` | Steward rationale |

## API Expectations

- `GET /imports/lookup-candidates/{import_job_id}` returns candidate list + pending count.
- `POST /imports/lookup-candidates/{candidate_id}/review` records steward decision.
- Apply endpoint must fail fast with pending-candidate detail.

## Controls

- No free-form governed writes in apply path.
- Lookup values created from approvals are auditable.
- Import completion report includes accepted/rejected/pending counts.

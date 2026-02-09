# Open Questions

## Data Model
- What is the final survivorship priority across ERP and procurement systems?
- Which fields are mandatory at `submitted` versus `approved` states?
- How should vendor merges be represented for historical analytics continuity?
- What is the approved vendor-offering hierarchy model for portfolio reporting?

## Security
- Which user groups require exception-based access to restricted columns?
- Is row-level scope determined only by org assignment, or also by geography/legal entity?
- What is the formal approval chain for policy exceptions?

## Pipeline
- Which sources can provide CDC versus snapshot only?
- What are accepted ingestion windows and blackout periods during close?
- What are acceptable data freshness SLAs per source?
- Which spreadsheet feeds are approved and who owns each template contract?

## Application
- Which workflows are mandatory for go-live versus post go-live?
- Which notifications are required (email, Slack, ticketing integration)?
- Are external users required in Phase 1?
- Which screens are visible for users with default limited read-only access?

## Operations
- Who owns after-hours incident response?
- What are production support SLAs by severity?
- What is the archive strategy for retired vendor records?

## Decision Tracking
- Log each resolved question as an ADR in `decisions/`.
- Cross-reference related docs and implementation tickets.

# Architecture Kickoff Checklist

## Participants
- Product owner for Vendor Catalog.
- Procurement operations lead.
- Finance/AP lead.
- Compliance and risk lead.
- Security and IAM lead.
- Data platform owner.
- Source system owners (ERP, procurement, risk tools).

## Inputs Required
- Current vendor onboarding process and policies.
- Existing vendor datasets and source ownership.
- Source specifics for PeopleSoft, Zycus, and spreadsheet feeds.
- Current access control model and identity provider group strategy.
- Compliance requirements (SOX, GDPR, CCPA, internal policy).
- Existing data retention standards.

## Workshop Agenda
1. Confirm business outcomes and success metrics.
2. Confirm in-scope processes and out-of-scope boundaries.
3. Review domain entities and required attributes.
4. Review access model and sensitive data classes.
5. Review ingestion patterns and SLA expectations.
6. Review implementation phases and team ownership.

## Readiness Gates Before Build
- Scope and success metrics signed.
- Canonical vendor ID strategy approved.
- Single-schema `twvendor` naming and table convention approved.
- Source-to-target mapping v1 approved.
- Role model and grant model approved.
- Environments and release model approved.
- Initial backlog for Phase 1 approved.

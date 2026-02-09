# Implementation Roadmap

## Phase 0 - Mobilize (2 Weeks)
- Finalize scope, owners, and success metrics.
- Complete source inventory and access prerequisites.
- Approve canonical vendor identity strategy.

## Phase 1 - Foundation (3 Weeks)
- Create single-schema Unity Catalog structure (`twvendor`) and baseline grants.
- Set up Databricks Asset Bundle and environment pipelines.
- Create reference and security mapping tables.

## Phase 2 - Core Data Domain (4 Weeks)
- Build source-to-core ingestion for PeopleSoft, Zycus, and spreadsheet feeds.
- Implement core vendor, ownership, offering, demo, and contract tables with quality checks.
- Publish first secure Vendor 360 serving views.

## Phase 3 - Workflow App (4 Weeks)
- Implement onboarding request and approval modules.
- Implement stewardship and change request modules.
- Implement access request workflow and audit views.

## Phase 4 - Hardening And Rollout (3 Weeks)
- Validate NFR targets and security control tests.
- Pilot with one business unit and collect feedback.
- Execute production rollout and hypercare.

## Milestones
- M1: Architecture sign-off.
- M2: Foundation deployed in dev and stage.
- M3: Vendor 360 secure serving views released.
- M4: Workflow app pilot complete.
- M5: Production go-live.

## Team Roles
- Solution architect.
- Data engineer.
- Analytics engineer.
- App engineer.
- Security engineer.
- Product owner.
- QA lead.

## First 30 Days Deliverables
- Approved architecture docs and ADR baseline.
- Catalog and schema bootstrap scripts.
- Source-to-target mapping for top 2 sources.
- Minimum viable security role model.

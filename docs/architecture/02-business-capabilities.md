# Business Capabilities

## Capability Map
- Vendor onboarding intake and validation.
- Vendor due diligence and risk review.
- Vendor approval and activation.
- Vendor profile maintenance and change control.
- Vendor ownership and application portfolio mapping.
- Demo tracking, scoring, and rejection rationale.
- Contract lifecycle and cancellation reasoning.
- Vendor access governance and audit.
- Vendor analytics for spend, risk, and compliance.

## Core Workflows

## Onboarding
1. Requestor submits onboarding request with required metadata.
2. System validates mandatory fields and duplicate candidates.
3. Tasks route to Procurement, Finance, Risk, Legal, and Security as needed.
4. Approvers record decisions with reason codes and timestamps.
5. Approved vendor is activated and published to secure serving views.

## Change Request
1. Steward or requestor submits change request.
2. Impacted fields drive approval path and controls.
3. Approved changes update current records and append history and audit events.

## Access Request
1. User submits access request tied to role and business justification.
2. Owner approval and Databricks group assignment are tracked.
3. Permissions are granted through Unity Catalog roles and secure views.
4. Users without explicit grant remain limited view-only in allowed screens.

## Demo Evaluation
1. Team logs vendor demos tied to vendor and offering.
2. Scoring rubric captures weighted score by category.
3. Non-selection reason and notes are captured for future reference.

## Contract Cancellation
1. Team records contract cancellation event and effective date.
2. Cancellation reasons and supporting notes are captured.
3. Vendor lifecycle state and audit event log are updated.

## Ownership And Portfolio
- One vendor can own many offerings or applications.
- Each offering can have internal business owner assignments.
- Vendor and offering contacts are tracked separately.

## Stewardship
- Duplicate detection review queue.
- Missing mandatory attribute remediation queue.
- Expired compliance document review queue.

## Reporting Needs
- Vendor population trend by lifecycle state.
- Onboarding cycle time by business unit.
- Open approval backlog and SLA breaches.
- Vendor risk distribution and overdue reassessments.
- Spend concentration by vendor/category/org.
- Demo outcomes and rejection reason trends.
- Contract cancellation trends by reason and business unit.

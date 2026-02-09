# Non-Functional Requirements

## Availability And Reliability
- Serving view query availability target: 99.9 percent monthly.
- Pipeline success target: 99.5 percent scheduled runs.
- RPO target: 4 hours for critical vendor master entities.
- RTO target: 8 hours for critical serving views.

## Performance
- Vendor profile retrieval p95 below 2 seconds.
- Search query p95 below 3 seconds for standard filters.
- Onboarding queue page load p95 below 4 seconds.

## Scalability
- Support at least 10 million vendor-related records in `twvendor`.
- Support concurrent analyst usage during monthly close windows.

## Security And Compliance
- Full audit trail for access and critical data changes.
- Encryption at rest and in transit.
- Periodic entitlement recertification and policy review.

## Data Quality
- Required fields completeness above 98 percent.
- Referential integrity violations below 0.1 percent.
- Duplicate vendor rate below 1 percent.

## Test Strategy
- Unit tests for transformation logic and state transitions.
- Integration tests for source-to-core and core-to-serving flows.
- Access tests for role, row, and column controls.
- Performance tests for dashboard and app interaction paths.

## Operability
- Runbooks for incident response and pipeline recovery.
- Alerting with on-call ownership by severity.
- Standard operational review cadence with KPI tracking.

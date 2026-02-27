# Risk Register

| ID | Risk | Impact | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Inconsistent vendor IDs across source systems | High | High | Canonical ID strategy and survivorship rules before build | Data Architect |
| R2 | Delayed source integration approvals | High | Medium | Early dependency tracking and executive escalation path | Product Owner |
| R3 | Overly broad access to sensitive fields | High | Medium | Secure views, masks, periodic entitlement review | Security Lead |
| R4 | Poor data quality from source feeds | High | High | Quality expectations, quarantine process, stewardship queue | Data Engineering Lead |
| R5 | Workflow complexity causes adoption friction | Medium | Medium | Pilot with one BU and simplify required fields | Product Owner |
| R6 | Performance issues on large vendor history | Medium | Medium | Optimize storage layout and serving views, load tests | Platform Lead |
| R7 | Regulatory requirement changes mid-project | Medium | Low | Compliance check-ins and ADR updates each sprint | Compliance Lead |

## Review Cadence
- Review weekly during implementation.
- Re-score impact and likelihood at each phase gate.

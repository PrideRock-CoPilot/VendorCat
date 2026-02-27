# Archive Access Protocol

## Archived Artifacts
- Legacy application source snapshots
- Legacy production data exports
- Historical deployment bundles

## Ownership
- Archive owner: Platform Engineering
- Security owner: Security Operations

## Retention
- Minimum retention: 365 days
- Review cadence: quarterly

## Access Workflow
1. Request archive access ticket with business justification.
2. Security owner approves temporary access window.
3. Archive owner provides read-only retrieval link.
4. Access is revoked after window expiry.

## Restore Workflow
1. Open restore request with specific artifact identifiers.
2. Validate target environment and purpose.
3. Restore to isolated non-production workspace.
4. Record restore event metadata (who/when/what).

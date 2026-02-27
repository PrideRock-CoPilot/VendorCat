# Legacy Decommission Plan

## Scope
This plan covers decommissioning legacy runtime paths after successful cutover to the Django rebuild runtime.

## Checklist
1. Confirm rebuild cutover smoke suite green in local and Databricks profiles.
2. Disable legacy runtime deployment entrypoints.
3. Remove legacy runtime traffic routes from load balancer/service config.
4. Mark legacy environment variables as deprecated.
5. Archive legacy logs and runtime diagnostics.
6. Verify no active jobs depend on legacy APIs.
7. Publish decommission completion note with owner and timestamp.

## Post-Decommission Validation
- Rebuild `/api/v1/health/live` and `/api/v1/health/ready` remain green.
- Mutation endpoint permission checks continue to pass.
- Databricks smoke workflow remains green.

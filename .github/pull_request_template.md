## Description

<!-- Provide a brief description of the changes in this PR -->

Fixes # (issue)

## Type of Change

<!-- Mark the appropriate type with an 'x' -->

- [ ] Bug fix
- [ ] New feature
- [ ] Schema change
- [ ] Refactor
- [ ] Security fix
- [ ] Documentation update

## Definition of Done Checklist

<!-- Select the appropriate checklist based on the type of change -->

### Bug Fix

- [ ] Root cause identified and documented
- [ ] Fix implemented
- [ ] Regression test added
- [ ] Manual test passed
- [ ] No new errors introduced
- [ ] Audit impact assessed
- [ ] Changelog updated

### Feature

- [ ] Requirements documented
- [ ] RBAC enforced (all mutation endpoints have permission checks)
- [ ] Input validated (all user inputs validated)
- [ ] Audit trail added (mutations log to audit_entity_change)
- [ ] Tests written (unit + integration for happy path + errors)
- [ ] Test coverage >= 80%
- [ ] UI tested manually
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Security review (if handles sensitive data)

### Schema Change

- [ ] Migration file created (setup/databricks/migration_NNN_description.sql)
- [ ] Migration number incremented sequentially
- [ ] Version table updated in migration
- [ ] Backward compatibility assessed
- [ ] Rollback plan documented in migration comments
- [ ] Applied to dev environment
- [ ] Repository updated for new schema
- [ ] Tests updated and passing
- [ ] Schema reference docs updated
- [ ] Changelog updated

### Refactor

- [ ] Refactor goal documented
- [ ] Behavior preserved (no functional changes)
- [ ] All existing tests pass without modification
- [ ] Performance measured (if perf refactor)
- [ ] No new lint/type violations
- [ ] Manual smoke test passed
- [ ] Documentation updated (if API changed)
- [ ] Tech debt issue closed

### Security Fix

- [ ] Vulnerability documented (CVE, Dependabot alert)
- [ ] Severity assessed
- [ ] Fix applied
- [ ] Exploit test added
- [ ] All tests pass
- [ ] Manual security test (exploit blocked)
- [ ] Related dependencies updated
- [ ] Changelog updated
- [ ] Deployed within SLO (<7 days for critical)

## Testing

<!-- Describe the tests you ran and how to reproduce -->

### Manual Testing

- [ ] Tested locally
- [ ] Tested in dev environment

### Automated Testing

- [ ] All existing tests pass
- [ ] New tests added and passing
- [ ] Coverage threshold met (>=80%)

## Screenshots (if applicable)

<!-- Add screenshots for UI changes -->

## Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] CI checks passing

## Rollback Plan

<!-- Describe how to rollback this change if needed -->

## Additional Notes

<!-- Any additional information for reviewers -->

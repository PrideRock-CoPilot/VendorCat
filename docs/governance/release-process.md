# Release Process

This document defines the VendorCatalog release workflow from feature branch to production deployment.

## Branch Strategy

**Main Branches**:
- `main`: Production-ready code, always deployable
- `develop`: Integration branch for features (future use)

**Feature Branches**:
- Pattern: `feature/short-description` or `feature/issue-number-description`
- Created from: `main`
- Merged to: `main` via Pull Request
- Example: `feature/modularization-overhaul`, `feature/234-vendor-contact-priority`

**Hotfix Branches**:
- Pattern: `hotfix/issue-number-description`
- Created from: `main`
- Merged to: `main` via fast-tracked PR
- Example: `hotfix/456-fix-contact-deletion-500`

**Release Tags**:
- Pattern: `vYYYY.MM.DD` or semantic `vMAJOR.MINOR.PATCH`
- Example: `v2026.02.15` or `v1.4.2`
- Created on: `main` branch after merge

## Pull Request Requirements

### PR Creation Checklist

1. **Branch naming**: Follow `feature/*` or `hotfix/*` pattern
2. **PR title**: Concise, descriptive (e.g., "Add vendor contact prioritization")
3. **PR description**: Include appropriate Definition of Done checklist
4. **Link issue**: Reference issue number in description (`Fixes #234`)
5. **Self-review**: Review your own diff before requesting review

### PR Approval Requirements

- **Minimum reviewers**: 1 (Tech Lead for architecture changes)
- **CI checks**: All must pass (tests, lint, coverage, RBAC)
- **Checklist complete**: All DoD boxes checked
- **Conflicts resolved**: No merge conflicts with `main`

### CI Quality Gates (Must Pass)

See [CI Quality Gates](../operations/ci-quality-gates.md) for details:
- Pytest (all tests pass)
- Coverage >= 80%
- Ruff linting
- MyPy type checking
- RBAC coverage test
- Security scan (future)

## Merge Process

1. **PR approved**: Reviewer approves PR
2. **Merge strategy**: Squash and merge (clean commit history)
3. **Commit message**: Use PR title for squash commit message
4. **Delete branch**: Delete feature branch after merge
5. **Tag release**: If user-facing change, tag with version

## Versioning Strategy

**Calendar Versioning** (recommended for internal tools):
- Format: `vYYYY.MM.DD` (e.g., `v2026.02.15`)
- Suffix for same-day releases: `v2026.02.15-2`

**Semantic Versioning** (if preferred):
- Format: `vMAJOR.MINOR.PATCH` (e.g., `v1.4.2`)
- MAJOR: Breaking changes (schema incompatibility, API changes)
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

**Version in Code**:
- Maintain `__version__ = "2026.02.15"` in `app/main.py`
- Display in UI footer and `/health` endpoint

## Deployment Workflow

### Pre-Deployment Checklist

- [ ] All tests pass in CI
- [ ] Code reviewed and approved
- [ ] PR merged to `main`
- [ ] Release tagged
- [ ] Changelog updated
- [ ] Schema migrations ready (if applicable)
- [ ] Rollback plan documented

### Deployment Steps

**Dev Environment** (optional, for testing):
1. Pull latest `main`
2. Apply migrations: `python setup/databricks/render_sql.py && python setup/databricks/validate_schema_and_bootstrap_admin.py`
3. Restart app: `python -m app.main`
4. Smoke test: Verify key features work

**Staging Environment** (if exists):
1. Deploy to staging Databricks workspace
2. Apply migrations
3. Run E2E tests: `python tests/e2e/live_browser_smoke.py`
4. Stakeholder review

**Production Environment**:
1. **Backup**: Export current schema and data
2. **Deploy code**: Sync to production app server
3. **Apply migrations**: Run migration scripts in order
4. **Verify schema version**: `SELECT * FROM twvendor.app_schema_version ORDER BY applied_at DESC LIMIT 1`
5. **Restart app**: Deploy new version
6. **Health check**: `curl https://vendorcat.example.com/health`
7. **Smoke test**: Manually verify critical paths (login, search, create vendor)
8. **Monitor**: Watch logs and metrics for 30 minutes

### Post-Deployment

- Update `docs/CHANGELOG.md` with deployment timestamp
- Communicate deployment to stakeholders (email, Slack)
- Monitor error rates and user feedback for 24 hours
- Close related GitHub issues

## Rollback Process

**When to Rollback**:
- Critical bug discovered in production
- Deployment causes data corruption
- Performance degradation (>2x latency)
- User-reported blocking issue

**Rollback Steps**:

1. **Immediate**: Revert to previous app version (restart with old code)
2. **Schema rollback** (if migrations applied):
   - Check migration file for rollback SQL (in comments)
   - Execute rollback DDL
   - Update `app_schema_version` to previous version
3. **Data restoration** (if data corrupted):
   - Restore from pre-deployment backup
   - Replay audit log to recover changes since backup
4. **Verify**: Run smoke tests, check health endpoint
5. **Communicate**: Notify stakeholders of rollback and ETA for fix
6. **Post-mortem**: Document incident, update rollback plan

**Rollback Decision Matrix**:

| Severity | Rollback Decision | Timeline |
|----------|------------------|----------|
| Critical (data loss, auth bypass, outage) | Immediate rollback | <15 min |
| High (major feature broken, >10% users affected) | Rollback unless fix ready in <1 hour | <30 min |
| Medium (minor feature broken, <10% users affected) | Forward fix preferred | <24 hours |
| Low (cosmetic, edge case) | Forward fix | Next release |

## Hotfix Process

For urgent production fixes:

1. **Create hotfix branch** from `main`: `git checkout -b hotfix/456-fix-critical-bug`
2. **Implement minimal fix**: Smallest change to resolve issue
3. **Test locally**: Verify fix + run full test suite
4. **Fast-track PR**: Request immediate review from Tech Lead
5. **CI must pass**: No exceptions even for hotfixes
6. **Merge and deploy**: Squash merge to `main`, deploy immediately
7. **Tag hotfix**: Use version with patch increment (e.g., `v2026.02.15-hotfix-1`)
8. **Post-deployment monitor**: Watch for 1 hour
9. **Post-mortem**: Schedule retro within 48 hours, document learnings

## Release Communication

**Internal (Team)**:
- Slack message in #vendorcat-dev channel
- Include: Version, key changes, deployment timestamp, any actions needed

**External (Stakeholders)**:
- Email to stakeholder list
- Include: What changed (user-facing), how to access, who to contact for issues
- Template: `docs/templates/release-email.md` (to be created)

## Release Checklist Template

Copy this for each release:

```markdown
## Release vYYYY.MM.DD

- [ ] All PRs merged to `main`
- [ ] CI passing
- [ ] Changelog updated
- [ ] Version bumped in app/main.py
- [ ] Tag created: `git tag vYYYY.MM.DD && git push origin vYYYY.MM.DD`
- [ ] Migrations ready (if schema changes)
- [ ] Backup production data
- [ ] Deploy to production
- [ ] Schema version verified
- [ ] Health check passed
- [ ] Smoke test passed
- [ ] Stakeholders notified
- [ ] Monitoring for 24h
```

## Metrics to Track

- **Deployment frequency**: Target 1-2 per week
- **Lead time**: PR open to production (target <3 days)
- **Change failure rate**: Deployments requiring rollback (target <5%)
- **Mean time to recovery**: Rollback time (target <30 min)

Review metrics monthly in team retro.

---

Last updated: 2026-02-15

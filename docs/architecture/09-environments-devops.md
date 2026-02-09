# Environments And DevOps

## Environment Model
- `dev`: rapid iteration and early integration.
- `stage`: pre-production validation and UAT.
- `prod`: controlled release with strict access boundaries.

## Workspace And Catalog Strategy
- Separate workspaces per environment.
- Separate Unity Catalog catalogs per environment.
- Keep schema name fixed as `twvendor` in every environment catalog.
- Production catalog bound only to production workspace(s).

## CI/CD Approach
- Use Databricks Asset Bundles for declarative deployment.
- Promote from dev to stage to prod via pull-request gates.
- Block deployment if quality, security, or tests fail.

## Branching And Release
- Trunk-based or short-lived feature branches.
- Tagged releases for production promotions.
- Hotfix path with post-release review.

## Secrets And Configuration
- Store credentials in secret scopes.
- Use environment-specific variables and service principals.
- Avoid hardcoded endpoints, paths, or tokens.

## Change Management
- Track architecture decisions in `decisions/`.
- Require approved ADR for breaking data model changes.
- Use migration scripts for schema evolution.

## Operational Cadence
- Weekly release window for non-critical changes.
- Emergency release process for high-severity incidents.
- Monthly architecture and quality review.

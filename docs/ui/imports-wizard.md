# Imports Wizard UX Spec

## Objective
Refactor imports into a true step-based wizard with progressive disclosure while preserving existing backend endpoints and data flow.

## Step Model
1. Upload
- Select file(s) and source metadata.
- Auto-detect likely mode (strict vs wizard) from extension.

2. Identify and Configure
- Configure parser mode.
- Show advanced parser options only when needed (JSON/XML/delimited) or when explicitly expanded.
- Submit to `/imports/preview`.

3. Map Fields
- Keep source field/tag static.
- Map to canonical target fields grouped by staging area.
- Show mapping progress: mapped, unmapped, required remaining.
- Save and reuse mapping profiles through `/imports/remap`.

4. Validate
- Present row status summary (error/review/blocked/ready).
- Provide status filters and a direct return path to mapping.

5. Stage/Ingest
- Show bulk action defaults and merge reason.
- Show row-level action/merge controls.
- Execute `/imports/apply` actions.

## UX Rules
- Single primary action per step.
- Sticky stepper with Back/Next controls.
- Do not expose stage/apply operations before validation.
- Hide advanced parse controls by default.
- Keep target field controls searchable and grouped.

## Technical Constraints
- Keep FastAPI + Jinja templates.
- Keep existing endpoints:
  - `/imports/preview`
  - `/imports/remap`
  - `/imports/apply`
- Frontend behavior is progressive enhancement; server-rendered pages remain functional without JS.

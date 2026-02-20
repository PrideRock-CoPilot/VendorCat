# Imports V2 + Vendor Merge Center Test Cases

## Functional
1. XML nested/repeating record detection
- Input: XML with nested collection and repeated child nodes.
- Steps: Preview in wizard with `format_hint=auto`, then with explicit `xml_record_path`.
- Expected: multi-row parse (no row collapse), selector is resolved and shown in preview metadata.

2. Any-layout wide file + no-loss payload
- Input: 50+ source columns where only a subset is mapped.
- Steps: Preview and inspect staged row payload.
- Expected: mapped fields applied, unmapped fields retained in `unmapped_source_fields`, original row in `source_row_raw`.

3. Shared profile permissions
- Steps: non-admin attempts profile save/edit; admin attempts profile save/edit.
- Expected: non-admin denied for write, admin allowed, all import-capable users can read/use profile.

4. Legacy profile migration fallback
- Setup: user has `imports.mapping_profiles.v1` in user settings.
- Steps: open imports mapping screen.
- Expected: profiles are available from shared table after migration path executes, without data loss.

5. Bundle per-file remap
- Input: multi-file/zip bundle with vendor/invoice/payment files.
- Steps: switch selected bundle file and remap each file independently.
- Expected: remap state persists per file and apply order remains vendor -> offering -> project -> invoice -> payment.

6. Bundle apply blocked dependency behavior
- Input: preview rows flagged `blocked` before dependencies exist.
- Steps: apply bundle in dependency order.
- Expected: rows are attempted after upstream files apply; unresolved dependency rows remain staged/blocked with info message.

## Vendor Merge Center
7. Merge preview conflict coverage
- Setup: two vendors with differing scalar fields and colliding offering names.
- Steps: open merge preview.
- Expected: field conflicts and offering collision options are returned for review.

8. Merge execute full-graph reassignment
- Steps: execute merge with required conflict/offering decisions.
- Expected: linked rows reassigned to survivor, source vendor archived (`inactive`, `merged_into_vendor_id` set), no data loss.

9. Canonical redirect and visibility filters
- Steps: open merged source vendor detail URL, then vendor list with/without `include_merged`.
- Expected: source redirects to survivor detail, merged sources hidden by default and visible when include filter is enabled.

10. Lineage/audit traceability
- Steps: view vendor lineage/audit after merge.
- Expected: merge event, members, and decisions visible in lineage surfaces and workflow/audit logs.

## Regression
11. Imports existing flows
- Validate quick + wizard flows across CSV/TSV/JSON/XML.
- Expected: prior successful flows continue to work with no parser regressions.

12. Security role behavior
- Validate non-admin cannot access merge center endpoints.
- Validate admin can access merge preview/execute endpoints.
- Expected: route-level permission enforcement works as designed.

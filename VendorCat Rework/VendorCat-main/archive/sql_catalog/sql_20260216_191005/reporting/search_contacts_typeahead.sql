WITH src AS (
  SELECT
    vc.full_name,
    vc.email,
    vc.phone,
    vc.contact_type,
    vc.vendor_id,
    coalesce(v.display_name, v.legal_name, vc.vendor_id) AS vendor_display_name,
    vc.active_flag
  FROM {core_vendor_contact} vc
  LEFT JOIN {core_vendor} v
    ON vc.vendor_id = v.vendor_id

  UNION ALL

  SELECT
    oc.full_name,
    oc.email,
    oc.phone,
    oc.contact_type,
    vo.vendor_id,
    coalesce(v2.display_name, v2.legal_name, vo.vendor_id) AS vendor_display_name,
    oc.active_flag
  FROM {core_offering_contact} oc
  INNER JOIN {core_vendor_offering} vo
    ON oc.offering_id = vo.offering_id
  LEFT JOIN {core_vendor} v2
    ON vo.vendor_id = v2.vendor_id
)
SELECT
  trim(src.full_name) AS full_name,
  trim(coalesce(src.email, '')) AS email,
  trim(coalesce(src.phone, '')) AS phone,
  trim(coalesce(src.contact_type, '')) AS contact_type,
  src.vendor_id,
  src.vendor_display_name,
  count(*) AS usage_count,
  trim(src.full_name)
    || case when trim(coalesce(src.email, '')) <> '' then ' (' || trim(src.email) || ')' else '' end
    || case when trim(coalesce(src.phone, '')) <> '' then ' - ' || trim(src.phone) else '' end
    || ' [' || coalesce(src.vendor_display_name, src.vendor_id, 'Unknown Vendor') || ']' AS label
FROM src
WHERE {where_clause}
GROUP BY
  trim(src.full_name),
  trim(coalesce(src.email, '')),
  trim(coalesce(src.phone, '')),
  trim(coalesce(src.contact_type, '')),
  src.vendor_id,
  src.vendor_display_name
ORDER BY
  count(*) DESC,
  lower(trim(src.full_name)),
  lower(trim(coalesce(src.email, '')))
LIMIT {limit}

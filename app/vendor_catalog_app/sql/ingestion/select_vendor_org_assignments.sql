SELECT vendor_org_assignment_id, vendor_id, org_id, assignment_type, active_flag
FROM {core_vendor_org_assignment}
WHERE vendor_id = %s
ORDER BY active_flag DESC, org_id

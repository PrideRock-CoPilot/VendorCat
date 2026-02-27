UPDATE {core_vendor}
SET {set_clause},
    updated_at = %s,
    updated_by = %s
WHERE vendor_id = %s

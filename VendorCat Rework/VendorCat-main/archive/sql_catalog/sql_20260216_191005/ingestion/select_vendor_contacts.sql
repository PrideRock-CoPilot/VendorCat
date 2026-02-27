SELECT vendor_contact_id, vendor_id, contact_type, full_name, email, phone, active_flag
FROM {core_vendor_contact}
WHERE vendor_id = %s
ORDER BY full_name

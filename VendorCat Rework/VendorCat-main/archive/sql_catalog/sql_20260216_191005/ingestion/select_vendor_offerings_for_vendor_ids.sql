SELECT offering_id, vendor_id, offering_name, offering_type, lob, service_type, lifecycle_state
FROM {core_vendor_offering}
WHERE vendor_id IN ({vendor_ids_placeholders})
ORDER BY vendor_id, offering_name

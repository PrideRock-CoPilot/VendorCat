SELECT vendor_identifier_id, vendor_id, identifier_type, identifier_value, is_primary, country_code
FROM {core_vendor_identifier}
WHERE vendor_id = %s
ORDER BY is_primary DESC, identifier_type

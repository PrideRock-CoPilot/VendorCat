UPDATE {app_document_link}
SET {set_clause},
    updated_at = %s,
    updated_by = %s
WHERE doc_id = %s

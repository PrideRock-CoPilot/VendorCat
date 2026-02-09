UPDATE {app_document_link}
SET active_flag = false,
    updated_at = %s,
    updated_by = %s
WHERE doc_id = %s

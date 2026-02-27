SELECT doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, created_at, created_by, updated_at, updated_by
FROM {app_document_link}
WHERE entity_type = %s
  AND entity_id = %s
  AND coalesce(active_flag, true) = true
ORDER BY updated_at DESC

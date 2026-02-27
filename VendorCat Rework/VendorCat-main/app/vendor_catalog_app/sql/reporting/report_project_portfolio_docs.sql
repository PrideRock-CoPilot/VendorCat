SELECT entity_id, doc_id
FROM {app_document_link}
WHERE entity_type = 'project'
  AND coalesce(active_flag, true) = true

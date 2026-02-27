INSERT INTO {app_document_link}
  (doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

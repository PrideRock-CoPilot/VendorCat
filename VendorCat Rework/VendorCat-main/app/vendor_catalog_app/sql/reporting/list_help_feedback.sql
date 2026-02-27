SELECT
  feedback_id,
  article_id,
  article_slug,
  was_helpful,
  comment,
  user_principal,
  page_path,
  created_at
FROM {vendor_help_feedback}
ORDER BY created_at DESC
LIMIT {limit}
OFFSET {offset}

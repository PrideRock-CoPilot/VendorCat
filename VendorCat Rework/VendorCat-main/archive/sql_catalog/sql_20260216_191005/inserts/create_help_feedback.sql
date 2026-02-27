INSERT INTO {vendor_help_feedback} (
  feedback_id,
  article_id,
  article_slug,
  was_helpful,
  comment,
  user_principal,
  page_path,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?);

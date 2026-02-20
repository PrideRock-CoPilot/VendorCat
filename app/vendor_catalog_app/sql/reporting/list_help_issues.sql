SELECT
  issue_id,
  article_id,
  article_slug,
  issue_title,
  issue_description,
  page_path,
  user_principal,
  created_at
FROM {vendor_help_issue}
ORDER BY created_at DESC
LIMIT {limit}
OFFSET {offset}

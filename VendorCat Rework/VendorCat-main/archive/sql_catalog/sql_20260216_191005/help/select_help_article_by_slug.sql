SELECT
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
FROM {vendor_help_article}
WHERE lower(slug) = lower(?)
LIMIT 1;

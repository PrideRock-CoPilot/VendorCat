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
  updated_by
FROM {vendor_help_article}
ORDER BY section ASC, title ASC;

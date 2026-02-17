import re, pathlib
repo = pathlib.Path('D:/VendorCatalog')
source = repo / 'archive/schema_creation/databricks/001_create_databricks_schema.sql'
text = source.read_text(encoding='utf-8')
want = {
    'app_user_directory','app_user_settings','app_usage_log',
    'sec_role_definition','sec_role_permission','sec_user_role_map','sec_group_role_map','sec_user_org_scope',
    'audit_entity_change','audit_workflow_event','audit_access_event',
    'vendor_help_article','vendor_help_feedback','vendor_help_issue'
}
pattern = re.compile(r'(?is)create\s+table\s+if\s+not\s+exists\s+([^\s(]+)\s*\(.*?\);')
found = {}
for m in pattern.finditer(text):
    full_name = m.group(1)
    short = full_name.split('.')[-1].lower()
    if short in want:
        found[short] = m.group(0)
for n in sorted(want):
    print('---', n, 'FOUND' if n in found else 'MISSING')
print('\n\n'.join(found[k] for k in sorted(found)))

import re, pathlib
repo = pathlib.Path('D:/VendorCatalog')
source = repo / 'archive/schema_creation/local_db/sql/schema/001_schema.sql'
text = source.read_text(encoding='utf-8')
want = {
    'app_user_directory','app_user_settings','app_usage_log',
    'sec_role_definition','sec_role_permission','sec_user_role_map','sec_group_role_map','sec_user_org_scope',
    'audit_entity_change','audit_workflow_event','audit_access_event',
    'vendor_help_article','vendor_help_feedback','vendor_help_issue'
}
pattern = re.compile(r'(?is)create\s+table\s+if\s+not\s+exists\s+([a-zA-Z0-9_\.]+)\s*\(.*?\);')
found = {}
for m in pattern.finditer(text):
    name = m.group(1).lower()
    if name in want:
        found[name] = m.group(0)
for n in sorted(want):
    print('---', n, 'FOUND' if n in found else 'MISSING')
print('\n'.join(found[k] for k in sorted(found)))

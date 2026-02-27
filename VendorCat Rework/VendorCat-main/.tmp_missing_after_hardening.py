import re, pathlib
repo=pathlib.Path('D:/VendorCatalog')
old=(repo/'archive/schema_creation/local_db/sql/schema/001_schema.sql').read_text(encoding='utf-8')
new='\n'.join(p.read_text(encoding='utf-8') for p in sorted((repo/'setup/v1_schema/local_db').glob('*.sql')))
pat=re.compile(r'(?im)^\s*create\s+table\s+(if\s+not\s+exists\s+)?([a-zA-Z0-9_\.]+)')
old_tables=sorted({m.group(2).lower() for m in pat.finditer(old)})
new_tables=sorted({m.group(2).lower() for m in pat.finditer(new)})
missing=[t for t in old_tables if t not in new_tables]
print('missing_count',len(missing))
for t in missing:
    print(t)

import re, pathlib
repo=pathlib.Path('D:/VendorCatalog')
sql_files=list((repo/'app/vendor_catalog_app/sql').rglob('*.sql'))
ph=re.compile(r'\{([a-zA-Z0-9_]+)\}')
placeholders=set()
for f in sql_files:
    txt=f.read_text(encoding='utf-8')
    placeholders.update(ph.findall(txt))
# candidate table-like placeholders
skip={'where_clause','search_filter','sort_column','sort_direction','status_filter','vendor_filter','q_clause','limit_clause','offset_clause'}
cands=sorted(p for p in placeholders if p not in skip and p.islower())
# gather v1 tables/views
ddl='\n'.join(p.read_text(encoding='utf-8') for p in (repo/'setup/v1_schema/local_db').glob('*.sql'))
tables=set(m.group(2).lower() for m in re.finditer(r'(?im)^\s*create\s+table\s+(if\s+not\s+exists\s+)?([a-zA-Z0-9_\.]+)',ddl))
views=set(m.group(2).lower() for m in re.finditer(r'(?im)^\s*create\s+view\s+(if\s+not\s+exists\s+)?([a-zA-Z0-9_\.]+)',ddl))
missing=[p for p in cands if p not in tables and p not in views]
print('placeholders',len(cands))
print('missing',len(missing))
for m in missing:
    print(m)

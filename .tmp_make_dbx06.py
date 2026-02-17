import pathlib,re
repo=pathlib.Path('D:/VendorCatalog')
src=(repo/'setup/v1_schema/local_db/06_create_functional_runtime_compat.sql').read_text(encoding='utf-8')
# Remove pragma and comments at top
src=re.sub(r'(?im)^PRAGMA\s+foreign_keys\s*=\s*ON;\s*\n','',src)
# Type mapping
mapped=src.replace('TEXT','STRING').replace('INTEGER','INT').replace('REAL','DOUBLE')
# Convert create-table terminator to Delta
mapped=re.sub(r'\);\s*',') USING DELTA;\n\n',mapped)
header='USE CATALOG `${CATALOG}`;\nUSE SCHEMA `${SCHEMA}`;\n\n-- Transitional runtime compatibility layer (Wave 1b).\n-- Databricks counterpart of local runtime parity tables.\n\n'
out=repo/'setup/v1_schema/databricks/06_create_functional_runtime_compat.sql'
out.write_text(header+mapped.strip()+'\n',encoding='utf-8')
print('wrote',out)

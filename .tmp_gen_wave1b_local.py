import re, pathlib
repo=pathlib.Path('D:/VendorCatalog')
src=(repo/'archive/schema_creation/local_db/sql/schema/001_schema.sql').read_text(encoding='utf-8')
out=repo/'setup/v1_schema/local_db/06_create_functional_runtime_compat.sql'
needed={
'app_access_request','app_document_link','app_employee_directory','app_lookup_option','app_note','app_offering_data_flow','app_offering_invoice','app_offering_profile','app_offering_ticket','app_onboarding_approval','app_onboarding_request','app_onboarding_task','app_project','app_project_demo','app_project_note','app_project_offering_map','app_project_vendor_map','app_vendor_change_request','core_contract','core_contract_event','core_offering_business_owner','core_offering_contact','core_vendor','core_vendor_business_owner','core_vendor_contact','core_vendor_demo','core_vendor_demo_note','core_vendor_demo_score','core_vendor_identifier','core_vendor_offering','core_vendor_org_assignment','hist_contract','hist_vendor','hist_vendor_offering','src_ingest_batch','src_peoplesoft_vendor_raw','src_spreadsheet_vendor_raw','src_zycus_vendor_raw'
}
pat=re.compile(r'(?is)create\s+table\s+if\s+not\s+exists\s+([a-zA-Z0-9_\.]+)\s*\(.*?\);')
blocks=[]
for m in pat.finditer(src):
    name=m.group(1).lower()
    if name in needed:
        blocks.append((name,m.group(0).strip()))
missing=sorted(needed-{n for n,_ in blocks})
if missing:
    raise SystemExit('Missing defs: '+', '.join(missing))
header="PRAGMA foreign_keys = ON;\n\n-- Transitional runtime compatibility layer (Wave 1b).\n-- These tables preserve existing application behavior during canonical V1 migration.\n\n"
out.write_text(header+'\n\n'.join(b for _,b in blocks)+'\n',encoding='utf-8')
print('wrote',out)
print('tables',len(blocks))

import sqlite3
con=sqlite3.connect(r'D:/VendorCatalog/setup/local_db/twvendor_local_v1_parity.db')
cur=con.cursor()
cur.execute("select count(*) from sqlite_master where type='table' and name not like 'sqlite_%'")
print('table_count', cur.fetchone()[0])
cur.execute("select name from sqlite_master where type='table' and name in ('app_user_directory','sec_user_role_map','audit_entity_change','vendor_help_article') order by 1")
print('bridge_tables', [r[0] for r in cur.fetchall()])

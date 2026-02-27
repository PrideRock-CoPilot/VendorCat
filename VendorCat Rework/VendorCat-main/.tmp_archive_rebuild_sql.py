from pathlib import Path
from datetime import datetime
import shutil
repo=Path('D:/VendorCatalog')
src=repo/'app/vendor_catalog_app/sql'
if not src.exists():
    raise SystemExit('SQL folder not found')
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
archive=repo/f'archive/sql_catalog/sql_{stamp}'
archive.parent.mkdir(parents=True, exist_ok=True)
shutil.move(str(src), str(archive))
# rebuild fresh folder from archived baseline
shutil.copytree(str(archive), str(src))
print('archived_to', archive)
print('rebuilt_to', src)

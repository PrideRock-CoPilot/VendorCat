from __future__ import annotations

import os
import sys
from pathlib import Path

import django

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vendorcatalog_rebuild.settings")
django.setup()

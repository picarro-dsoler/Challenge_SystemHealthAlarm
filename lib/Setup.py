"""Initialize the SystemHealthAlarm SQLite database and table schemas."""

import sys
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
_R2_ROOT = _LIB_DIR.parent
_PACKAGES = _LIB_DIR.parents[3] / "packages"

for entry in (_PACKAGES, _R2_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from lib.AlarmTableList import dbo
from lib.config import ALARM_CONN   


for table_name in dbo.keys():
    dbo[table_name].reinit_table()
    print(f"Reinitialized table {table_name}")

print("Setup complete")
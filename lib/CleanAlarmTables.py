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
from lib.config import DB_PATH

db_path = str((_R2_ROOT / DB_PATH).resolve())
(_R2_ROOT / DB_PATH).parent.mkdir(parents=True, exist_ok=True)

print(db_path)

table_skip_list = ["SurveyData"]
for table_name in dbo.keys():
    if table_name not in table_skip_list:
        dbo[table_name].reinit_table(arguments={"db_path": db_path})
        print(f"Reinitialized table {table_name}")

print("Reinitialized tables complete")
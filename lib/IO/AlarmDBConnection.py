from locallib.picarrodb import *
import os
import sqlite3
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

_lib_dir = os.path.abspath(os.path.dirname(__file__))
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

_SQLITE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEFAULT_DB_RELATIVE = os.path.join("database", "SystemHealthAlarm_Alarms.db")


def connect_sqlite(db_path):
    """Open a SQLite connection used by KPIHub.

    Geometry columns (datatype='geometry' in table defs) are stored as WKT TEXT.
    Values should be written as WKT strings (e.g. from SQL Server Shape.STAsText()
    or shapely .wkt); SpatiaLite is not required.
    """
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.text_factory = str
    return conn


class SQLiteConnection(PConnection):
    def __init__(self, host):
        self.host = host
        self.dbtype = "sqlite"
        self.engine = connect_sqlite(host)


class PostgreSQLConnection(DataHubConnection):
    def __init__(self, host: str, database: str, user: str, password: str):
        super().__init__(host, database, user, password)

    def set_engine(self):
        return super().set_engine()


db_path = os.path.abspath(os.path.join(_SQLITE_ROOT, _DEFAULT_DB_RELATIVE))
print(db_path)
ALARM_SQLite_Conn = SQLiteConnection(db_path)
ALARM_PostgreSQL_Conn = PostgreSQLConnection(
    host=os.getenv("ALARM_HOST"),
    database=os.getenv("ALARM_DATABASE"),
    user=os.getenv("ALARM_USER"),
    password=os.getenv("ALARM_PASSWORD"),
)
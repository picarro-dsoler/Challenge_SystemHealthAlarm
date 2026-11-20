from locallib.query import Query
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lib.config import ALARM_CONN
from lib.IO.AlarmDBConnection import PostgreSQLConnection
from lib.AlarmTableList import column_name_map


def unified_query(sql, connection=ALARM_CONN):
    df = Query(query=sql).execute(connection)
    if isinstance(connection, PostgreSQLConnection):
        df = unify_columns(df)
    return df

def unify_columns(df):
    df.columns = [column_name_map[str(col).lower()] for col in df.columns]
    # Uppercase UUID-style identifier columns only (not e.g. IdleTimeMinutes).
    for col in df.columns:
        if col == "Id" or col.endswith("Id"):
            df[col] = df[col].astype(str).str.upper()
    return df
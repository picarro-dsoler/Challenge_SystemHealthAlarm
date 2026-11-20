from locallib.picarrodb import *
from locallib.query import Query
from lib.IO.AlarmDBConnection import *
import sqlite3
import uuid
from datetime import date, datetime, time
import pandas as pd


# SQL Server-style datatypes (IngesterTables / DBColumn) -> DDL types per engine.
# SQLite: geometry as WKT TEXT; other types pass through (SQLite affinity).
SQLITE_TYPE_MAP = {
    'geometry': 'TEXT',
    'time': 'TEXT',
    'uniqueidentifier': 'TEXT',
}

# Postgres: map T-SQL names to valid PostgreSQL types (PostGIS for geometry).
POSTGRES_TYPE_MAP = {
    'uniqueidentifier': 'UUID',
    'nvarchar': 'TEXT',
    'bit': 'BOOLEAN',
    'datetime': 'TIMESTAMP',
    'date': 'DATE',
    'int': 'INTEGER',
    'bigint': 'BIGINT',
    'float': 'DOUBLE PRECISION',
    'time': 'TIME',
    'geometry': 'geometry',
}

# Postgres only: column nagitmes that cannot appear unquoted next to their type (e.g. Date DATE).
_PG_QUOTE_COLUMNS = frozenset({"Date", "LocalTime"})


class AlarmTable(DBTable):
    def __init__(self, name, columns = None, connection = None):
        super().__init__(name, columns)
        self.sql_list = {}
        self.connection = connection

    @staticmethod
    def sqlite_column_type(datatype):
        if datatype is None:
            return 'TEXT'
        return SQLITE_TYPE_MAP.get(datatype, datatype)

    @staticmethod
    def postgres_column_type(datatype):
        if datatype is None:
            return 'TEXT'
        return POSTGRES_TYPE_MAP.get(datatype, datatype)

    def ddl_column_type(self, datatype):
        if isinstance(self.connection, PostgreSQLConnection):
            return self.postgres_column_type(datatype)
        return self.sqlite_column_type(datatype)

    @staticmethod
    def _pg_ident(name):
        return '"' + str(name).replace('"', '""') + '"'

    def get_name(self, name):
        return self._sql_ident(name)

    def _sql_ident(self, name):
        if isinstance(self.connection, PostgreSQLConnection) and name in _PG_QUOTE_COLUMNS:
            return self._pg_ident(name)
        return name

    def delete_table(self):
        if isinstance(self.connection, SQLiteConnection):
            #Delete table syntax for the SQLite database
            try:
                Query(f"DROP TABLE IF EXISTS {self.name}").execute(self.connection, return_df=False)
            except Exception as e:
                raise e
        elif isinstance(self.connection, PostgreSQLConnection):
            #Delete table syntax for the PostgreSQL database
            try:
                Query(f"DROP TABLE IF EXISTS {self.name} CASCADE").execute(
                    self.connection, return_df=False
                )
            except Exception as e:
                raise e
        else:
            raise ValueError("Connection is not a SQLite or PostgreSQL connection")
 
    def create_table(self, arguments = None, commit = True):
        col_defs_list = []
        primary_keys = []
        for column in self.columns:
            col_type = self.ddl_column_type(column.datatype)
            col_def = f"{self._sql_ident(column.name)} {col_type}"
            if getattr(column, "key", None) == "primary":
                primary_keys.append(column.name)
            col_defs_list.append(col_def)
        col_defs = ", ".join(col_defs_list)
        if primary_keys:
            pk_list = ", ".join(self._sql_ident(n) for n in primary_keys)
            col_defs += f", PRIMARY KEY ({pk_list})"
        if arguments is not None and 'pair_key' in arguments and arguments['pair_key'] is not None:
            pair_list = ", ".join(self._sql_ident(n) for n in arguments['pair_key'])
            col_defs += f", PRIMARY KEY ({pair_list})"
        sql = f"CREATE TABLE IF NOT EXISTS {self._sql_ident(self.name)} ({col_defs})"
        Query(sql).execute(self.connection, return_df = False)

        return sql

    def reinit_table(self, arguments=None, extra_sql=None):
        self.delete_table()
        self.create_table(arguments=arguments if arguments is not None else {'pair_key': None})

    def query_table(self):
        from lib.query.kpi_query import unified_query

        return unified_query(f"SELECT * FROM {self.name}", self.connection)

    def sql(self, query = 'create', db_type= 'postgres'):
        if db_type == 'postgres':
            return self.sql_list[query]
        else:
            return self.sql_list[query]

    @staticmethod
    def _bind_value(val, for_sqlite=False):
        """Convert DataFrame cell values to DBAPI-friendly Python types."""
        if pd.isna(val):
            return None
        if isinstance(val, pd.Timestamp):
            val = val.to_pydatetime()
        if isinstance(val, datetime):
            return val.isoformat() if for_sqlite else val
        if isinstance(val, time):
            return val.isoformat()
        if isinstance(val, date):
            return val.isoformat() if for_sqlite else val
        if isinstance(val, uuid.UUID):
            return str(val) if for_sqlite else val
        if hasattr(val, "wkt") and not isinstance(val, (str, bytes, bytearray)):
            return val.wkt
        if isinstance(val, (bytes, bytearray)):
            return bytes(val)
        if hasattr(val, "item"):
            return val.item()
        return val

    def _upsert_sql(self, cols, pk_cols, primary_key):
        is_pg = isinstance(self.connection, PostgreSQLConnection)
        table = self._sql_ident(self.name)
        if is_pg:
            column_list = ", ".join(self._sql_ident(c) for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            pk_names = primary_key if isinstance(primary_key, list) else [primary_key]
            conflict_targets = ", ".join(self._sql_ident(c) for c in pk_names)
            update_set = ", ".join(
                f"{self._sql_ident(col)}=EXCLUDED.{self._sql_ident(col)}"
                for col in cols
                if col not in pk_cols
            )
        else:
            column_list = ", ".join(cols)
            placeholders = ", ".join(["?"] * len(cols))
            pk_names = primary_key if isinstance(primary_key, list) else [primary_key]
            conflict_targets = ", ".join(pk_names)
            update_set = ", ".join(
                f"{col}=excluded.{col}" for col in cols if col not in pk_cols
            )
        return (
            f"INSERT INTO {table} ({column_list}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT({conflict_targets}) DO UPDATE SET {update_set}"
        )

    def update_table(self, arguments = None):
        df = arguments["DataFrame"]
        primary_key = arguments["PrimaryKey"]
        if isinstance(primary_key, list):
            pk_cols = set(primary_key)
        elif isinstance(primary_key, str):
            pk_cols = {primary_key}
        else:
            raise ValueError("PrimaryKey must be a list of strings or a single string")

        cols = df.columns.tolist()
        insert_sql = self._upsert_sql(cols, pk_cols, primary_key)

        if isinstance(self.connection, SQLiteConnection):
            for_sqlite = True
            data = [
                tuple(self._bind_value(row[col], for_sqlite=for_sqlite) for col in cols)
                for _, row in df.iterrows()
            ]
            conn = self.connection.engine
            cursor = conn.cursor()
            cursor.executemany(insert_sql, data)
            conn.commit()
            cursor.close()
        elif isinstance(self.connection, PostgreSQLConnection):
            for_sqlite = False
            data = [
                tuple(self._bind_value(row[col], for_sqlite=for_sqlite) for col in cols)
                for _, row in df.iterrows()
            ]
            raw = self.connection.engine.raw_connection()
            cursor = None
            try:
                cursor = raw.cursor()
                cursor.executemany(insert_sql, data)
                raw.commit()
            finally:
                if cursor is not None:
                    cursor.close()
                raw.close()
        else:
            raise ValueError("Connection is not a SQLite or PostgreSQL connection")

    def delete_data(self, arguments=None):
        """
        Deletes rows from the table where the primary key(s) match the provided value(s).
        Uses self.connection (SQLite or PostgreSQL on the table object).

        arguments must contain:
            - 'PrimaryKey' (str or list): column(s) to match
            - 'KeyValues' (list of dict or DataFrame): keys to delete
        """
        if arguments is None:
            raise ValueError("Arguments are required")
        if "PrimaryKey" not in arguments:
            raise ValueError("PrimaryKey is required")
        if "KeyValues" not in arguments:
            raise ValueError("KeyValues is required (list of dicts or DataFrame)")

        primary_key = arguments["PrimaryKey"]
        key_values = arguments["KeyValues"]

        if isinstance(primary_key, list):
            pk_cols = primary_key
        elif isinstance(primary_key, str):
            pk_cols = [primary_key]
        else:
            raise ValueError("PrimaryKey must be a list of strings or a single string")

        if isinstance(key_values, pd.DataFrame):
            keys_list = key_values[pk_cols].to_dict(orient="records")
        elif isinstance(key_values, list):
            keys_list = key_values
        else:
            raise ValueError("KeyValues must be a DataFrame or list of dicts")

        is_pg = isinstance(self.connection, PostgreSQLConnection)
        placeholder = "%s" if is_pg else "?"
        table = self._sql_ident(self.name)
        where_clause = " AND ".join(
            f"{self._sql_ident(col)} = {placeholder}" for col in pk_cols
        )
        sql = f"DELETE FROM {table} WHERE {where_clause}"

        for_sqlite = isinstance(self.connection, SQLiteConnection)
        values_list = [
            tuple(
                self._bind_value(key_dict.get(col), for_sqlite=for_sqlite)
                for col in pk_cols
            )
            for key_dict in keys_list
        ]

        if not values_list:
            return

        if isinstance(self.connection, SQLiteConnection):
            conn = self.connection.engine
            cursor = conn.cursor()
            cursor.executemany(sql, values_list)
            conn.commit()
            cursor.close()
        elif isinstance(self.connection, PostgreSQLConnection):
            raw = self.connection.engine.raw_connection()
            cursor = None
            try:
                cursor = raw.cursor()
                cursor.executemany(sql, values_list)
                raw.commit()
            finally:
                if cursor is not None:
                    cursor.close()
                raw.close()
        else:
            raise ValueError("Connection is not a SQLite or PostgreSQL connection")
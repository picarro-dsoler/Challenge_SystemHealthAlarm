"""Alarm SQLite table definitions built with ``AlarmTable`` / ``DBColumn``."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from locallib.picarrodb.PicarroDBClass import DBColumn
from config import *
from lib.AlarmTable import AlarmTable


dbo = {}
#--- ConfigParams table -------------------------------------------------------
dbo['ConfigParams'] = AlarmTable("ConfigParams", connection=ALARM_CONN)
dbo['ConfigParams'].add_column(DBColumn("SurveyorUnitId", datatype="nvarchar", key='primary'))
for key in ALL_CONFIG_PARAMS_DEFAULT.keys():
    dbo['ConfigParams'].add_column(DBColumn(key, datatype="float"))
dbo['ConfigParams'].add_column(DBColumn("LastUpdate", datatype="datetime"))

#--- SurveyData table -------------------------------------------------------
for table in TABLE_LIST:
    table_name = table['Name']
    table_columns = table['Columns']
    table_primary_key = table['PrimaryKey']
    dbo[table_name] = AlarmTable(table_name, connection=ALARM_CONN)
    for col in table_columns.keys():
        if col == table_primary_key and not isinstance(table_primary_key, list):
            dbo[table_name].add_column(DBColumn(col, datatype=table_columns[col], key='primary'))
        else:
            dbo[table_name].add_column(DBColumn(col, datatype=table_columns[col]))

column_name_map = {}
for _table in dbo.values():
    for c in _table.columns:
        column_name_map[c.name.lower()] = c.name

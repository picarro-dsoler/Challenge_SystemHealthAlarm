import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from typing import Any


from lib.IO.AlarmDBConnection import SQLiteConnection, PostgreSQLConnection
from lib.AlarmTableList import dbo
from lib.config import *

import pandas as pd
from locallib.query import Query
from locallib.pandas import *
from lib.query.kpi_query import unify_columns


class Detector:
    def __init__(self, detector_table_config: dict[str, Any],  config_cols: list[str]):
        self.name = detector_table_config['Name']
        self.detector_table_config = detector_table_config
        self.survey_data_table_config = SURVEYDATA_TABLE
        self.config_cols = config_cols
        self.first_index = None

        self.survey_data = None
        self.detector_data = None
        self.sandbox_data = None
        self.config_data =None

    def init_detector_data(self, sandbox_data: pd.DataFrame):
        #For all the values that have NaN fill the preset values
        try:
            for col in self.detector_table_config['DefaultValues']:
                sandbox_data[col] = sandbox_data[col].fillna(self.detector_table_config['DefaultValues'][col])
            return sandbox_data
        except KeyError:
            raise ValueError("DefaultValues is not properly set in config files")

    def set_surveyor_unit(self, customer_id: str, surveyor_unit_id: str): 
        self.customer_id = customer_id
        self.surveyor_unit_id = surveyor_unit_id

    def load_data(self, args={"resource": ALARM_CONN}):
        resource = args["resource"]
        if isinstance(resource, SQLiteConnection) or isinstance(resource, PostgreSQLConnection):
            self.survey_data = Query(
                f"SELECT * FROM {self.survey_data_table_config['Name']} WHERE SurveyorUnitId = '{self.surveyor_unit_id}'"
            ).execute(resource)
            if len(self.survey_data) == 0:
                raise ValueError("No data found")
            self.survey_data.db.set_query(f"SELECT * FROM {self.detector_table_config['Name']} WHERE SurveyId IN (SELECT SurveyId FROM temp_survey)")
            if isinstance(resource, SQLiteConnection):
                source_col = 'SurveyId'
            else:
                source_col = 'surveyid'
            self.detector_data = self.survey_data.db.execute(resource, source_col = source_col, temp_table_name = 'temp_survey')
            self.detector_data = unify_columns(self.detector_data)
            if not all(col in self.detector_data.columns for col in self.detector_table_config['Columns'].keys()):
                raise ValueError(f"Data missing columns: {self.detector_table_config['Columns'].keys()}")
            self.survey_data = unify_columns(self.survey_data)
            self.detector_data = unify_columns(self.detector_data)
        elif isinstance(resource, pd.DataFrame):
            self.survey_data = resource
            self.detector_data = pd.DataFrame(columns=self.detector_table_config['Columns'])
            if not all(col in self.survey_data.columns for col in ['SurveyId', 'SurveyorUnit', 'RawDurationMinutes', 'StartDateTime','EndDateTime', 'PeakCount', 'AverageFlowRate', 'PeakMinutes']):
                raise ValueError(f"Data missing columns")
        elif resource is None:
            self.detector_data = pd.DataFrame(columns=self.detector_table_config['Columns'])
        else:
            raise ValueError("Resource must be SQLiteConnection or DataFrame")

        self._reorder_data()


    def _reorder_data(self):
        self.survey_data = self.survey_data.sort_values("StartDateTime").reset_index(drop=True)
        self.sandbox_data = pd.merge(self.survey_data, self.detector_data, on='SurveyId', how='left')
        self.sandbox_data = self.init_detector_data(self.sandbox_data)
        n_last_update_na = self.sandbox_data["LastUpdate"].isna().sum()
        print(n_last_update_na)
        if n_last_update_na == 0:
            self.first_index = -1
        else:
            self.first_index = self.sandbox_data.index[0]

    def load_config(self, args={"resource": ALARM_CONN}):
        resource = args["resource"]
        if isinstance(resource, SQLiteConnection) or isinstance(resource, PostgreSQLConnection):
            self.config_data = Query(
                f"SELECT * FROM ConfigParams WHERE SurveyorUnitId = '{self.surveyor_unit_id}'"
            ).execute(resource)
            self.config_data = unify_columns(self.config_data)
        elif isinstance(resource, pd.DataFrame):
            self.config_data = resource.reset_index(drop=True)
        if self.config_data is None or len(self.config_data) == 0:
            raise ValueError("Config is empty")
        if not all(col in self.config_data.columns for col in self.config_cols):
            raise ValueError(f"Config missing columns: {self.config_cols}")
        self.config_data = self.config_data[self.config_cols]

    def run_detector(self, resource=None, write_back=True):
        if self.first_index == -1:
            print(f"No data to run detector {self.name}")
        else:
           start = self.first_index
           end = len(self.sandbox_data)
           print(f"Running detector {self.name} from index {start} to {end}")
           for i in range(start, end):
             self.update(i)
             self.sandbox_data.loc[i, 'LastUpdate'] = pd.Timestamp.now()
           if write_back:
            self.write_local_data()

    def update(self, i):
        pass

    def write_local_data(self):
        output_data = self.sandbox_data[self.detector_table_config['Columns'].keys()]
        dbo[self.detector_table_config['Name']].update_table(
            arguments={"DataFrame": output_data, "PrimaryKey": "SurveyId"}
        )

    def plot_data(self):
        pass
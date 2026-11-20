import numpy as np
import pandas as pd

from lib.Detector.Detector import Detector
from lib.config import FAULT_TABLE, FAULT_CONFIG_PARAMS_DEFAULT, ALARM_CONN
from lib.IO.AlarmDBConnection import SQLiteConnection, PostgreSQLConnection

from lib.query.kpi_query import unify_columns

class FaultDetector(Detector):
    def __init__(self,):
        super().__init__(
            detector_table_config=FAULT_TABLE,
            config_cols=FAULT_CONFIG_PARAMS_DEFAULT.keys(),
        )

    def load_data(self,args: dict = {"resource": ALARM_CONN}):
        #If the resource is a list of detectors, then merge the detector data into the sandbox data.
        if isinstance(args['resource'], list):
            for idx, detector in enumerate(args['resource']):
                if idx == 0:
                    self.sandbox_data = detector.sandbox_data
                    self.sandbox_data.rename(columns={'LastUpdate': detector.name + 'LastUpdate'}, inplace=True)
                else:
                    temp_data = detector.sandbox_data[list(detector.detector_table_config['Columns'].keys())]
                    temp_data.rename(columns={'LastUpdate': detector.name + 'LastUpdate'}, inplace=True)
                    self.sandbox_data = pd.merge(self.sandbox_data, temp_data, on='SurveyId', how='left')
            #Add the columns of default_table_config['Columns'] to the sandbox_data
            #First add the columns
            for col in self.detector_table_config['Columns'].keys():
                self.sandbox_data[col] = None

        #If the resource is an Alarm_Conn object, then load the data from the database the surveyor unit should be set
        elif isinstance(args['resource'], SQLiteConnection) or isinstance(args['resource'], PostgreSQLConnection):
            super().load_data(args=args)
            if isinstance(args['resource'], PostgreSQLConnection):
                source_col = 'surveyid'
            else:
                source_col = 'SurveyId'
                self.survey_data.rename(columns={'SurveyId': source_col}, inplace=True)
            subdetector_data = pd.DataFrame()
            for idx, detector in enumerate(FAULT_TABLE['DetectorColumns']):
                table_name = detector.split('.')[0]
                column_name = detector.split('.')[1]
                self.survey_data.db.set_query(f"SELECT SurveyId, {column_name} FROM {table_name} WHERE SurveyId IN (SELECT SurveyId FROM temp_survey)")
                temp_data = self.survey_data.db.execute(args['resource'], source_col = source_col, temp_table_name = 'temp_survey')
                temp_data = unify_columns(temp_data)
                if idx == 0:
                    subdetector_data = temp_data
                else:
                    subdetector_data = pd.merge(subdetector_data, temp_data, on='SurveyId', how='inner')
            self.sandbox_data = pd.merge(self.sandbox_data, subdetector_data, on='SurveyId', how='left')

        self.sandbox_data = self.init_detector_data(self.sandbox_data)
        n_last_update_na = self.sandbox_data["LastUpdate"].isna().sum()
        print(n_last_update_na)
        if n_last_update_na == 0:
            self.first_index = -1
        else:
            self.first_index = self.sandbox_data.index[0]

    def load_config(self, args={"resource": ALARM_CONN}):
        super().load_config(args=args)
        row = self.config_data.iloc[0]
        self.fault_threshold = float(row["FaultThreshold"])


    def update(self, i):
        self.sandbox_data.loc[i, "FaultH"] = self.sandbox_data.loc[i, "FlowrateH"] * self.sandbox_data.loc[i, "PeakI"]


    def run_detector(self, resource=None, write_back=True):
        super().run_detector(resource=resource, write_back=write_back)
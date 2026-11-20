import matplotlib.pyplot as plt
from locallib.picarrodb import *
from locallib.query import *
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lib.AlarmTableList import dbo

class SurveyQAReader:
    def __init__(self, customer_name, starting_date, ending_date):
        self.customer_name = customer_name
        self.customer_id = None
        self.starting_date = starting_date
        self.ending_date = ending_date
        self.Conn_dict = {
            'EU1': EU1_Conn,
            'EU2': EU2_Conn,
            'NA': US_Conn,
        }   
        self.conn = None
        self.peak_survey = pd.DataFrame()

        self._get_survey_qa_data()

    def _get_survey_qa_data(self):
        #Get the databse where the customer is located
        for conn in self.Conn_dict:
            q = Query(
                f"SELECT 1 AS Flag, Id as CustomerId FROM Customer "
                f"WHERE LOWER(Name) = LOWER('{self.customer_name}')"
            ).execute(self.Conn_dict[conn])
            if q.empty:
                continue
            if q["Flag"].iloc[0] == 1:
                self.conn = conn
                self.customer_id = q["CustomerId"].iloc[0]
                print(f"Customer {self.customer_name} found in {self.conn} database")
                break
        if self.conn is None:
            print(f"Customer {self.customer_name} not found in any database — skipping")
            return
        a = get_users(customer_name = self.customer_name, user_table = '#TempUser')
        b = get_surveys(user_table = '#TempUser', survey_table = '#TempSurvey', start_date = self.starting_date, end_date = self.ending_date)
        b.set_child(Query(
            query = (
                "SELECT "
                "COUNT(P.Id) AS PeakCount, "
                "P.SurveyId, "
                "SQA.AverageFlowRate "
                "INTO #TempPeak "
                "FROM Peak P "
                "LEFT JOIN SurveyQACheck SQA ON P.SurveyId = SQA.SurveyId "
                "WHERE P.SurveyId IN (SELECT SurveyId FROM #TempSurvey) "
                "GROUP BY P.SurveyId, SQA.AverageFlowRate"
            )
        ))
        a.set_child(b)
        data = a.execute(self.Conn_dict[self.conn], table_return = ['#TempUser', '#TempPeak', '#TempSurvey'])
        peak_survey = pd.merge(data['#TempSurvey'][['SurveyId','AnalyzerSerialNumber', 'SurveyorUnitId', 'SurveyorUnit','RawDurationMinutes','StartDateTime','EndDateTime']], data['#TempPeak'][['PeakCount', 'SurveyId', 'AverageFlowRate']], on = 'SurveyId', how = 'left')
        peak_survey['AverageFlowRate'] = peak_survey['AverageFlowRate'].astype(float)
        peak_survey['PeakCount'] = [0 if pd.isna(x) else int(x) for x in peak_survey['PeakCount']]
        peak_survey['RawDurationMinutes'] = [0 if pd.isna(x) else float(x) for x in peak_survey['RawDurationMinutes']]
        peak_survey['PeakMinutes'] = peak_survey['PeakCount'] / peak_survey['RawDurationMinutes']

        peak_survey.dropna(subset=['AverageFlowRate'], inplace=True)
        # Actually, here it *is* assigned: self.peak_survey is set to a copy of peak_survey.
        # If you expected peak_survey to be assigned instead, it is, just above in this function.
        # This line assigns a fresh copy of the DataFrame to the instance variable for later use.
        peak_survey["CustomerId"] = self.customer_id
        peak_survey["CustomerName"] = self.customer_name
        self.peak_survey = peak_survey.copy()

    def get_cars(self):
        return list(self.peak_survey['SurveyorUnit'].unique())

    def get_car_data(self, surveyor_unit=None) -> pd.DataFrame:
        """Return survey rows; index is MultiIndex (SurveyorUnit, original index) when multiple cars."""
        chunks: dict = {}
        if surveyor_unit is None:
            surveyor_units = self.get_cars()
        else:
            surveyor_units = [surveyor_unit]
        for unit in surveyor_units:
            part = self.peak_survey[self.peak_survey["SurveyorUnit"] == unit].sort_values(
                "StartDateTime"
            ).reset_index(drop=True)
            chunks[unit] = part
        if not chunks:
            return pd.DataFrame()
        # Dict keys become the first index level (surveyor unit name)
        return pd.concat(chunks, names=["SurveyorUnit"])

    def update_local_data(self, local_data_resoruce):
        if self.peak_survey.empty or self.customer_id is None:
            return
        conn = local_data_resoruce
        data = Query(
            f"SELECT SurveyId FROM SurveyData WHERE CustomerId = '{self.customer_id}'"
        ).execute(conn)
        missing_data = self.peak_survey[
            ~self.peak_survey["SurveyId"].isin(data["SurveyId"])
        ]
        if missing_data.empty:
            return

        table_cols = [col.name for col in dbo['SurveyData'].columns]
        missing_data = missing_data.reindex(columns=table_cols)

        db_path = str(Path(__file__).resolve().parents[2] / DB_PATH)
        dbo['SurveyData'].update_table(
            arguments={"db_path": db_path, "DataFrame": missing_data, "PrimaryKey": "SurveyId"}
        )
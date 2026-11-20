import sys
import os
import sys
from locallib.picarrodb import *
from locallib.query import *

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from lib.IO.SruveyQAReader import SurveyQAReader
from lib.AlarmTableList import dbo
from lib.config import *
from lib.query.kpi_query import unified_query
import pandas as pd
if __name__ == "__main__":
    for conn in CONN_DICT:
        #data = Query(f"SELECT Id as CustomerId, Name as CustomerName FROM Customer WHERE Active = 1 AND Name != 'Italgas'").execute(CONN_DICT[conn])
        data = Query(f"SELECT Id as CustomerId, Name as CustomerName FROM Customer WHERE Active = 1").execute(CONN_DICT[conn])
        #print(data)
        for _,row in data.iterrows():
            customer_id = row['CustomerId']
            customer_name = row['CustomerName']
            print('Updating data for customer: ', customer_name)
            new_surveys = SurveyQAReader(customer_name, starting_date = '2025-01-01', ending_date = '2026-12-31').peak_survey
            local_surveys = unified_query(f"SELECT SurveyId FROM SurveyData WHERE CustomerId = '{customer_id}'")
            missing_surveys = new_surveys[~new_surveys['SurveyId'].isin(local_surveys['SurveyId'])]
            missing_surveys['RetrivedDate'] = pd.Timestamp.now()
            print('Adding ', len(missing_surveys), ' surveys to the database')
            dbo['SurveyData'].update_table(arguments={'DataFrame': missing_surveys, 'PrimaryKey': 'SurveyId'})



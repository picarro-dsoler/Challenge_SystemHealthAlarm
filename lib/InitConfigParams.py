import sys
import os
import sys
from locallib.picarrodb import *
from locallib.query import *
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lib.AlarmTableList import dbo
from lib.config import *
from lib.query.kpi_query import unified_query
if __name__ == "__main__":
    surveyors = unified_query(f'SELECT DISTINCT SurveyorUnitId FROM SurveyData')
    config = unified_query(f'SELECT * FROM ConfigParams')
    missing_configs = surveyors[~surveyors['SurveyorUnitId'].isin(config['SurveyorUnitId'])]
    for key, value in ALL_CONFIG_PARAMS_DEFAULT.items():
        missing_configs[key] = value
    dbo['ConfigParams'].update_table(
        arguments={"DataFrame": missing_configs, "PrimaryKey": "SurveyorUnitId"}
    )
    print("ConfigParams initialized")
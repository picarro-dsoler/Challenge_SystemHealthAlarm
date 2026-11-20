from locallib.picarrodb import *
from lib.IO.AlarmDBConnection import ALARM_PostgreSQL_Conn, ALARM_SQLite_Conn

#--- Connection parameters
CONN_DICT = {'EU1':EU1_Conn, 'EU2': EU2_Conn}
ALARM_CONN = ALARM_SQLite_Conn


# Default config parameters of the detectors
FLOWRATE_CONFIG_PARAMS_DEFAULT = {
    "WindowSize": 10,
    "Alpha0": 0.01,
    "Beta0": 0.01,
    "Sigma": 0.05,
    "deltaXThreshold": 0.2,
    "AlertRate": 0.99,
}

PEAKMIN_CONFIG_PARAMS_DEFAULT = {
    "WindowSize": 10,
    "WindowMeasured": 30,
    "Alpha0": 0.01,
    "Beta0": 0.1,
    "PriorWeightPrev": 1,
    "PriorWeightCut": 1,
    "LambdaThreshold": 0.05,
}

FAULT_CONFIG_PARAMS_DEFAULT = {
    "FaultThreshold": 0.90,
}

# Shared keys (e.g. NWindowSize) appear once — flowrate wins on conflict.
ALL_CONFIG_PARAMS_DEFAULT = {
    **PEAKMIN_CONFIG_PARAMS_DEFAULT,
    **FLOWRATE_CONFIG_PARAMS_DEFAULT,
    **FAULT_CONFIG_PARAMS_DEFAULT,
}

#DB Column structure
SURVEYDATA_TABLE = {
    'Name' : 'SurveyData',
    'Columns' : {
        'CustomerId': 'uniqueidentifier',
        'CustomerName': 'nvarchar',
        'SurveyorUnit': 'nvarchar',
        'SurveyorUnitId': 'uniqueidentifier',
        'SurveyId': 'uniqueidentifier',
        'AnalyzerSerialNumber': 'nvarchar',
        'StartDateTime': 'datetime',
        'EndDateTime': 'datetime',
        'AverageFlowRate': 'float',
        'PeakCount': 'float',
        'PeakMinutes': 'float',
        'RawDurationMinutes': 'float',
        'RetrivedDate': 'datetime',
        },
    'PrimaryKey' : 'SurveyId',
}

FAULT_TABLE = {
    'Name' : 'FaultDetector',
    'Columns' : {
        'SurveyId' : 'uniqueidentifier',
        'FaultH' : 'float',
        'LastUpdate' : 'datetime',
    },
    'PrimaryKey' : 'SurveyId',
    'DefaultValues' : {
        'FaultH' : 0,
    },
    'DetectorColumns' : ['FlowRateDetector.FlowrateH', 'PeakMinDetector.PeakI'],
}
FLOWRATE_TABLE = {
    'Name' : 'FlowRateDetector',
    'Columns' : {
        'SurveyId' : 'uniqueidentifier',
        'FlowrateS' : 'float',
        'FlowrateSpred' : 'float',
        'FlowrateDx' : 'float',
        'FlowrateDelta' : 'float',
        'FlowrateAlpha' : 'float',
        'FlowrateBeta' : 'float',
        'FlowrateI' : 'float',
        'FlowRateC' : 'float',
        'FlowrateH' : 'float',
        'FlowRateFlag' : 'boolean',
        'FlowRateNStep' : 'int',
        'LastUpdate' : 'datetime',
    },
    'DefaultValues' : {
        'FlowrateS' : 0,
        'FlowrateSpred' : 0,
        'FlowrateDx' : 0,
        'FlowrateDelta' : 0,
        'FlowrateAlpha' : 0,
        'FlowrateBeta' : 0,
        'FlowrateI' : 0,
        'FlowRateC' : 0,
        'FlowrateH' : 0,
        'FlowRateFlag' : False,
        'FlowRateNStep' : 0,
    },
    'PrimaryKey' : 'SurveyId',
}

PEAKMIN_TABLE = {
    'Name' : 'PeakMinDetector',
    'Columns' : {
        'SurveyId' : 'uniqueidentifier',
        'PeakS' : 'float',
        'PeakC' : 'float',
        'PeakI' : 'float',
        'PeakH' : 'float',
        'LastUpdate' : 'datetime',
    },
    'DefaultValues' : {
        'PeakS' : 0,
        'PeakC' : 0,
        'PeakI' : 0,
        'PeakH' : 0,
    },
    'PrimaryKey' : 'SurveyId',
}


TABLE_LIST = [SURVEYDATA_TABLE, FLOWRATE_TABLE, PEAKMIN_TABLE, FAULT_TABLE]
"""Latest customer per surveyor unit from local AlarmData (SQLite)."""

from pathlib import Path

import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from lib.query.kpi_query import unified_query
def get_latest_customer_per_surveyor_unit() -> pd.DataFrame:
    """
    Return unique ``SurveyorUnitId`` with ``CustomerId`` and ``SurveyorUnit`` from the
    most recent survey (by ``StartDateTime`` in ``AlarmData``).
    """
    df = unified_query(
        """
        SELECT SurveyorUnitId, SurveyorUnit, CustomerId, StartDateTime, CustomerName
        FROM SurveyData
        """)
    if df.empty:
        return pd.DataFrame(
            columns=["SurveyorUnitId", "SurveyorUnit", "CustomerId", "CustomerName", "StartDateTime"]
        )

    df["StartDateTime"] = pd.to_datetime(df["StartDateTime"], errors="coerce")
    df = df.dropna(subset=["StartDateTime"]).sort_values("StartDateTime")
    latest = (
        df.groupby("SurveyorUnitId", as_index=False)
        .agg(
            SurveyorUnit=("SurveyorUnit", "last"),
            CustomerId=("CustomerId", "last"),
            CustomerName=("CustomerName", "last"),
            StartDateTime=("StartDateTime", "last"),
        )
    )
    return latest.reset_index(drop=True)


if __name__ == "__main__":
    print(get_latest_customer_per_surveyor_unit())

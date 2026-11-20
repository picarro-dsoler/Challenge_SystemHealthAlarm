"""Survey / detector data — PostgreSQL (SystemHealth_EU) or optional SQLite file."""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from db_conn import connection_label, get_engine

_DEFAULT_DB = (
    Path(__file__).resolve().parent.parent / "database" / "SystemHealthAlarm_Alarms.db"
)
DB_PATH = Path(os.environ.get("ALARM_DB_PATH", _DEFAULT_DB))


def use_postgres() -> bool:
    return os.environ.get("ALARM_DB_BACKEND", "postgresql").lower() != "sqlite"


CONFIG_COLUMNS = [
    "WindowSize",
    "WindowMeasured",
    "Alpha0",
    "Beta0",
    "PriorWeightPrev",
    "PriorWeightCut",
    "LambdaThreshold",
    "Sigma",
    "deltaXThreshold",
    "AlertRate",
    "FaultThreshold",
]

CONFIG_DEFAULTS = {
    "WindowSize": 10.0,
    "WindowMeasured": 30.0,
    "Alpha0": 0.01,
    "Beta0": 0.01,
    "PriorWeightPrev": 1.0,
    "PriorWeightCut": 1.0,
    "LambdaThreshold": 0.05,
    "Sigma": 0.05,
    "deltaXThreshold": 0.2,
    "AlertRate": 0.99,
    "FaultThreshold": 0.90,
}

_COL_DISPLAY: dict[str, str] = {
    "customerid": "CustomerId",
    "customername": "CustomerName",
    "surveyorunitid": "SurveyorUnitId",
    "surveyorunit": "SurveyorUnit",
    "surveyid": "SurveyId",
    "startdatetime": "StartDateTime",
    "averageflowrate": "AverageFlowRate",
    "peakminutes": "PeakMinutes",
    "flowrateh": "FlowrateH",
    "peakh": "PeakH",
    "peaki": "PeakI",
    "faulth": "FaultH",
    "avgflowrate": "AvgFlowRate",
    "avgpeakminutes": "AvgPeakMinutes",
    "avgfaulth": "AvgFaultH",
    "surveycount": "SurveyCount",
    "lastupdate": "LastUpdate",
    **{c.lower(): c for c in CONFIG_COLUMNS},
}


def db_display_name() -> str:
    if use_postgres():
        return connection_label()
    return f"SQLite · {DB_PATH.name}"


def _sanitize_value(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, uuid.UUID):
        return str(val).upper()
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime().isoformat(sep=" ", timespec="seconds")
    if hasattr(val, "item") and not isinstance(val, (str, bytes)):
        try:
            return val.item()
        except (ValueError, AttributeError):
            pass
    return val


def _normalize_df(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    rows: list[dict] = []
    for _, series in df.iterrows():
        row: dict = {}
        for col, val in series.items():
            key = _COL_DISPLAY.get(str(col).lower(), str(col))
            row[key] = _sanitize_value(val)
        rows.append(row)
    return rows


def _pg_read(sql: str, params: tuple | list | None = None) -> list[dict]:
    """Run SQL via DBAPI (psycopg2) so %s params work with pandas."""
    engine = get_engine()
    raw = engine.raw_connection()
    try:
        df = pd.read_sql(sql, raw, params=tuple(params or ()))
    finally:
        raw.close()
    return _normalize_df(df)


def _sql_id(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def _pg_execute(sql: str, params: tuple | list) -> None:
    with get_engine().begin() as conn:
        conn.exec_driver_sql(sql, tuple(params))


def connect():
    """SQLite connection, or None when using PostgreSQL (queries use the shared engine)."""
    if use_postgres():
        return None
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def list_customers(conn: sqlite3.Connection | None = None) -> list[dict]:
    if use_postgres():
        return _pg_read(
            """
            SELECT DISTINCT customerid, customername
            FROM surveydata
            WHERE customerid IS NOT NULL
            ORDER BY customername
            """
        )
    rows = conn.execute(
        """
        SELECT DISTINCT CustomerId, CustomerName
        FROM SurveyData
        WHERE CustomerId IS NOT NULL
        ORDER BY CustomerName
        """
    ).fetchall()
    return [dict(r) for r in rows]


def list_surveyors(conn: sqlite3.Connection | None, customer_id: str | None = None) -> list[dict]:
    if use_postgres():
        sql = """
            SELECT DISTINCT surveyorunitid, surveyorunit
            FROM surveydata
            WHERE surveyorunitid IS NOT NULL
        """
        params: list = []
        if customer_id:
            sql += " AND customerid = %s"
            params.append(_sql_id(customer_id))
        sql += " ORDER BY surveyorunit"
        return _pg_read(sql, params)
    sql = """
        SELECT DISTINCT SurveyorUnitId, SurveyorUnit
        FROM SurveyData
        WHERE SurveyorUnitId IS NOT NULL
    """
    params = []
    if customer_id:
        sql += " AND CustomerId = ?"
        params.append(customer_id)
    sql += " ORDER BY SurveyorUnit"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def survey_metrics_by_surveyor(
    conn: sqlite3.Connection | None,
    surveyor_ids: list[str] | None = None,
    customer_id: str | None = None,
) -> list[dict]:
    if use_postgres():
        sql = """
            SELECT
                sd.surveyorunitid,
                sd.surveyorunit,
                sd.surveyid,
                sd.startdatetime,
                sd.averageflowrate,
                sd.peakminutes,
                COALESCE(fr.flowrateh, 0) AS flowrateh,
                COALESCE(pm.peaki, 0) AS peaki,
                COALESCE(fd.faulth, 0) AS faulth
            FROM surveydata sd
            LEFT JOIN flowratedetector fr ON fr.surveyid = sd.surveyid
            LEFT JOIN peakmindetector pm ON pm.surveyid = sd.surveyid
            LEFT JOIN faultdetector fd ON fd.surveyid = sd.surveyid
            WHERE sd.surveyorunitid IS NOT NULL
        """
        params: list = []
        if customer_id:
            sql += " AND sd.customerid = %s"
            params.append(_sql_id(customer_id))
        if surveyor_ids:
            placeholders = ",".join("%s" for _ in surveyor_ids)
            sql += f" AND sd.surveyorunitid IN ({placeholders})"
            params.extend(_sql_id(s) for s in surveyor_ids)
        sql += " ORDER BY sd.startdatetime"
        return _pg_read(sql, params)

    sql = """
        SELECT
            sd.SurveyorUnitId,
            sd.SurveyorUnit,
            sd.SurveyId,
            sd.StartDateTime,
            sd.AverageFlowRate,
            sd.PeakMinutes,
            COALESCE(fr.FlowrateH, 0) AS FlowrateH,
            COALESCE(pm.PeakI, 0) AS PeakI,
            COALESCE(fd.FaultH, 0) AS FaultH
        FROM SurveyData sd
        LEFT JOIN FlowRateDetector fr ON fr.SurveyId = sd.SurveyId
        LEFT JOIN PeakMinDetector pm ON pm.SurveyId = sd.SurveyId
        LEFT JOIN FaultDetector fd ON fd.SurveyId = sd.SurveyId
        WHERE sd.SurveyorUnitId IS NOT NULL
    """
    params = []
    if customer_id:
        sql += " AND sd.CustomerId = ?"
        params.append(customer_id)
    if surveyor_ids:
        placeholders = ",".join("?" * len(surveyor_ids))
        sql += f" AND sd.SurveyorUnitId IN ({placeholders})"
        params.extend(surveyor_ids)
    sql += " ORDER BY sd.StartDateTime"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def surveyor_latest_status(conn: sqlite3.Connection | None, customer_id: str) -> list[dict]:
    if use_postgres():
        return _pg_read(
            """
            WITH ranked AS (
                SELECT
                    sd.surveyorunitid,
                    sd.surveyorunit,
                    sd.surveyid,
                    sd.startdatetime,
                    COALESCE(fr.flowrateh, 0) AS flowrateh,
                    COALESCE(pm.peakh, 0) AS peakh,
                    COALESCE(fd.faulth, 0) AS faulth,
                    ROW_NUMBER() OVER (
                        PARTITION BY sd.surveyorunitid
                        ORDER BY sd.startdatetime DESC
                    ) AS rn
                FROM surveydata sd
                LEFT JOIN flowratedetector fr ON fr.surveyid = sd.surveyid
                LEFT JOIN peakmindetector pm ON pm.surveyid = sd.surveyid
                LEFT JOIN faultdetector fd ON fd.surveyid = sd.surveyid
                WHERE sd.customerid = %s
                  AND sd.surveyorunitid IS NOT NULL
            )
            SELECT
                surveyorunitid,
                surveyorunit,
                surveyid,
                startdatetime,
                flowrateh,
                peakh,
                faulth
            FROM ranked
            WHERE rn = 1
            ORDER BY surveyorunit
            """,
            (_sql_id(customer_id),),
        )

    rows = conn.execute(
        """
        WITH ranked AS (
            SELECT
                sd.SurveyorUnitId,
                sd.SurveyorUnit,
                sd.SurveyId,
                sd.StartDateTime,
                COALESCE(fr.FlowrateH, 0) AS FlowrateH,
                COALESCE(pm.PeakH, 0) AS PeakH,
                COALESCE(fd.FaultH, 0) AS FaultH,
                ROW_NUMBER() OVER (
                    PARTITION BY sd.SurveyorUnitId
                    ORDER BY sd.StartDateTime DESC
                ) AS rn
            FROM SurveyData sd
            LEFT JOIN FlowRateDetector fr ON fr.SurveyId = sd.SurveyId
            LEFT JOIN PeakMinDetector pm ON pm.SurveyId = sd.SurveyId
            LEFT JOIN FaultDetector fd ON fd.SurveyId = sd.SurveyId
            WHERE sd.CustomerId = ?
              AND sd.SurveyorUnitId IS NOT NULL
        )
        SELECT
            SurveyorUnitId,
            SurveyorUnit,
            SurveyId,
            StartDateTime,
            FlowrateH,
            PeakH,
            FaultH
        FROM ranked
        WHERE rn = 1
        ORDER BY SurveyorUnit
        """,
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def surveyor_latest_status_all(conn: sqlite3.Connection | None) -> list[dict]:
    if use_postgres():
        return _pg_read(
            """
            WITH ranked AS (
                SELECT
                    sd.customerid,
                    sd.customername,
                    sd.surveyorunitid,
                    sd.surveyorunit,
                    sd.surveyid,
                    sd.startdatetime,
                    COALESCE(fr.flowrateh, 0) AS flowrateh,
                    COALESCE(pm.peakh, 0) AS peakh,
                    COALESCE(fd.faulth, 0) AS faulth,
                    ROW_NUMBER() OVER (
                        PARTITION BY sd.customerid, sd.surveyorunitid
                        ORDER BY sd.startdatetime DESC
                    ) AS rn
                FROM surveydata sd
                LEFT JOIN flowratedetector fr ON fr.surveyid = sd.surveyid
                LEFT JOIN peakmindetector pm ON pm.surveyid = sd.surveyid
                LEFT JOIN faultdetector fd ON fd.surveyid = sd.surveyid
                WHERE sd.customerid IS NOT NULL
                  AND sd.surveyorunitid IS NOT NULL
            )
            SELECT
                customerid,
                customername,
                surveyorunitid,
                surveyorunit,
                surveyid,
                startdatetime,
                flowrateh,
                peakh,
                faulth
            FROM ranked
            WHERE rn = 1
            ORDER BY customername, surveyorunit
            """
        )

    rows = conn.execute(
        """
        WITH ranked AS (
            SELECT
                sd.CustomerId,
                sd.CustomerName,
                sd.SurveyorUnitId,
                sd.SurveyorUnit,
                sd.SurveyId,
                sd.StartDateTime,
                COALESCE(fr.FlowrateH, 0) AS FlowrateH,
                COALESCE(pm.PeakH, 0) AS PeakH,
                COALESCE(fd.FaultH, 0) AS FaultH,
                ROW_NUMBER() OVER (
                    PARTITION BY sd.CustomerId, sd.SurveyorUnitId
                    ORDER BY sd.StartDateTime DESC
                ) AS rn
            FROM SurveyData sd
            LEFT JOIN FlowRateDetector fr ON fr.SurveyId = sd.SurveyId
            LEFT JOIN PeakMinDetector pm ON pm.SurveyId = sd.SurveyId
            LEFT JOIN FaultDetector fd ON fd.SurveyId = sd.SurveyId
            WHERE sd.CustomerId IS NOT NULL
              AND sd.SurveyorUnitId IS NOT NULL
        )
        SELECT
            CustomerId,
            CustomerName,
            SurveyorUnitId,
            SurveyorUnit,
            SurveyId,
            StartDateTime,
            FlowrateH,
            PeakH,
            FaultH
        FROM ranked
        WHERE rn = 1
        ORDER BY CustomerName, SurveyorUnit
        """
    ).fetchall()
    return [dict(r) for r in rows]


def classify_surveyor_status(flowrate_h: float, peak_h: float, fault_h: float) -> tuple[str, str]:
    if fault_h > 0.8:
        return "red", "Critical"
    if peak_h > 0.5 or flowrate_h > 0.5:
        return "yellow", "Warning"
    return "green", "OK"


def surveyor_summary(conn: sqlite3.Connection | None) -> list[dict]:
    if use_postgres():
        return _pg_read(
            """
            SELECT
                sd.surveyorunitid,
                MAX(sd.surveyorunit) AS surveyorunit,
                AVG(sd.averageflowrate) AS avgflowrate,
                AVG(sd.peakminutes) AS avgpeakminutes,
                AVG(COALESCE(fd.faulth, 0)) AS avgfaulth,
                COUNT(*) AS surveycount
            FROM surveydata sd
            LEFT JOIN faultdetector fd ON fd.surveyid = sd.surveyid
            WHERE sd.surveyorunitid IS NOT NULL
            GROUP BY sd.surveyorunitid
            ORDER BY surveyorunit
            """
        )

    rows = conn.execute(
        """
        SELECT
            sd.SurveyorUnitId,
            MAX(sd.SurveyorUnit) AS SurveyorUnit,
            AVG(sd.AverageFlowRate) AS AvgFlowRate,
            AVG(sd.PeakMinutes) AS AvgPeakMinutes,
            AVG(COALESCE(fd.FaultH, 0)) AS AvgFaultH,
            COUNT(*) AS SurveyCount
        FROM SurveyData sd
        LEFT JOIN FaultDetector fd ON fd.SurveyId = sd.SurveyId
        WHERE sd.SurveyorUnitId IS NOT NULL
        GROUP BY sd.SurveyorUnitId
        ORDER BY SurveyorUnit
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_config(conn: sqlite3.Connection | None, surveyor_unit_id: str) -> dict:
    if use_postgres():
        cols = ", ".join(c.lower() for c in CONFIG_COLUMNS)
        rows = _pg_read(
            f"SELECT surveyorunitid, {cols}, lastupdate FROM configparams WHERE surveyorunitid = %s",
            (_sql_id(surveyor_unit_id),),
        )
        if not rows:
            out = {k: CONFIG_DEFAULTS[k] for k in CONFIG_COLUMNS}
            out["SurveyorUnitId"] = surveyor_unit_id
            return out
        return rows[0]

    row = conn.execute(
        "SELECT * FROM ConfigParams WHERE SurveyorUnitId = ?",
        (surveyor_unit_id,),
    ).fetchone()
    if row is None:
        out = {k: CONFIG_DEFAULTS[k] for k in CONFIG_COLUMNS}
        out["SurveyorUnitId"] = surveyor_unit_id
        return out
    return dict(row)


def upsert_config(conn: sqlite3.Connection | None, surveyor_unit_id: str, values: dict) -> None:
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    if use_postgres():
        col_names = ["surveyorunitid", *[c.lower() for c in CONFIG_COLUMNS], "lastupdate"]
        placeholders = ", ".join("%s" for _ in col_names)
        row_values = [_sql_id(surveyor_unit_id), *[values[c] for c in CONFIG_COLUMNS], now]
        update_set = ", ".join(f"{c.lower()} = EXCLUDED.{c.lower()}" for c in CONFIG_COLUMNS)
        sql = f"""
            INSERT INTO configparams ({", ".join(col_names)})
            VALUES ({placeholders})
            ON CONFLICT (surveyorunitid) DO UPDATE SET
                {update_set},
                lastupdate = EXCLUDED.lastupdate
        """
        _pg_execute(sql, row_values)
        return

    existing = conn.execute(
        "SELECT 1 FROM ConfigParams WHERE SurveyorUnitId = ?",
        (surveyor_unit_id,),
    ).fetchone()
    if existing:
        sets = ", ".join(f'"{col}" = ?' for col in CONFIG_COLUMNS)
        conn.execute(
            f'UPDATE ConfigParams SET {sets}, LastUpdate = ? WHERE SurveyorUnitId = ?',
            [values[col] for col in CONFIG_COLUMNS] + [now, surveyor_unit_id],
        )
    else:
        cols = ["SurveyorUnitId", *CONFIG_COLUMNS, "LastUpdate"]
        placeholders = ", ".join("?" * len(cols))
        conn.execute(
            f"INSERT INTO ConfigParams ({', '.join(cols)}) VALUES ({placeholders})",
            [surveyor_unit_id] + [values[col] for col in CONFIG_COLUMNS] + [now],
        )
    conn.commit()
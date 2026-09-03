from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

import pandas as pd
from locallib.picarrodb import EU1_Conn, EU2_Conn
from locallib.query import Query, get_surveys, get_users

PeakSurveySpec = Union["ExtractionSpec", Mapping[str, Any]]

_CONN_BY_NAME = {
    "EU1": EU1_Conn,
    "EU2": EU2_Conn,
}

__all__ = [
    "ExtractionSpec",
    "PeakSurveySpec",
    "EU1_Conn",
    "EU2_Conn",
    "fetch_peak_survey_data",
    "build_peak_survey",
    "filter_surveyor_unit",
    "append_to_parquet",
    "extract_multiple_data",
]


@dataclass(frozen=True)
class ExtractionSpec:
    customer_name: str
    start_date: str
    surveyor_unit: str
    case_id: str
    end_date: Optional[str] = None
    conn: Any = EU1_Conn


def _resolve_conn(conn: Any) -> Any:
    if isinstance(conn, str):
        resolved = _CONN_BY_NAME.get(conn.upper())
        if resolved is None:
            raise ValueError(f"Unknown conn '{conn}'. Use 'EU1', 'EU2', EU1_Conn, or EU2_Conn.")
        return resolved
    return conn


def _conn_cache_key(conn: Any) -> str:
    resolved = _resolve_conn(conn)
    return f"{resolved.host}:{resolved.database}"


def _peak_query() -> str:
    return (
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


def fetch_peak_survey_data(
    customer_name: str,
    start_date: str,
    conn: Any = EU1_Conn,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Query survey and peak data for a customer and return a merged peak_survey frame."""
    conn = _resolve_conn(conn)
    users = get_users(customer_name=customer_name, user_table="#TempUser")
    surveys = get_surveys(
        user_table="#TempUser",
        survey_table="#TempSurvey",
        start_date=start_date,
        end_date=end_date,
    )
    surveys.set_child(Query(query=_peak_query()))
    users.set_child(surveys)
    data = users.execute(conn, table_return=["#TempPeak", "#TempSurvey"])
    return build_peak_survey(data)


def build_peak_survey(data: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge survey and peak query results and compute PeakMinutes."""
    peak_survey = pd.merge(
        data["#TempSurvey"][
            ["SurveyId", "SurveyorUnit", "RawDurationMinutes", "StartDateTime", "EndDateTime"]
        ],
        data["#TempPeak"][["PeakCount", "SurveyId", "AverageFlowRate"]],
        on="SurveyId",
        how="left",
    )
    peak_survey["AverageFlowRate"] = peak_survey["AverageFlowRate"].astype(float)
    peak_survey = peak_survey.dropna(subset=["AverageFlowRate"])
    peak_survey["PeakMinutes"] = peak_survey["PeakCount"] / peak_survey["RawDurationMinutes"]
    return peak_survey


def filter_surveyor_unit(peak_survey: pd.DataFrame, surveyor_unit: str) -> pd.DataFrame:
    """Return rows for a single surveyor unit with a reset index."""
    return peak_survey[peak_survey["SurveyorUnit"] == surveyor_unit].reset_index(drop=True)


def append_to_parquet(new_data: pd.DataFrame, output_path: Union[str, Path]) -> pd.DataFrame:
    """Append rows to a parquet file, creating it when missing."""
    output_path = Path(output_path)
    if output_path.exists():
        total_data = pd.concat([pd.read_parquet(output_path), new_data], ignore_index=True)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_data = new_data.copy()
    total_data.to_parquet(output_path, index=False)
    return total_data


def _normalize_spec(spec: PeakSurveySpec, default_conn: Any = EU1_Conn) -> ExtractionSpec:
    if isinstance(spec, ExtractionSpec):
        return spec
    return ExtractionSpec(
        customer_name=spec["customer_name"],
        start_date=spec["start_date"],
        surveyor_unit=spec["surveyor_unit"],
        case_id=spec["case_id"],
        end_date=spec.get("end_date"),
        conn=spec.get("conn", default_conn),
    )


def extract_multiple_data(
    specs: Sequence[PeakSurveySpec],
    output_path: Union[str, Path],
    conn: Any = EU1_Conn,
) -> pd.DataFrame:
    """
    Extract one or more surveyor-unit cases and append them to a parquet file.

    Specs with the same customer, date range, and connection share a single query.
    """
    normalized = [_normalize_spec(spec, default_conn=conn) for spec in specs]
    query_cache: dict[tuple[str, str, Optional[str], str], pd.DataFrame] = {}
    extracted_frames = []

    for spec in normalized:
        spec_conn = _resolve_conn(spec.conn)
        cache_key = (spec.customer_name, spec.start_date, spec.end_date, _conn_cache_key(spec_conn))
        if cache_key not in query_cache:
            query_cache[cache_key] = fetch_peak_survey_data(
                customer_name=spec.customer_name,
                start_date=spec.start_date,
                conn=spec_conn,
                end_date=spec.end_date,
            )

        case_data = filter_surveyor_unit(query_cache[cache_key], spec.surveyor_unit).copy()
        case_data["CaseId"] = spec.case_id
        extracted_frames.append(case_data)

    if not extracted_frames:
        return pd.DataFrame()

    new_data = pd.concat(extracted_frames, ignore_index=True)
    return append_to_parquet(new_data, output_path)

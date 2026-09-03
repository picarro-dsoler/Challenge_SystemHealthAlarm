from __future__ import annotations

import time
from typing import Any, Optional

__all__ = ["run_athena_query"]


def run_athena_query(
    query: str,
    client: Any,
    db: str,
    wg: str,
    timeout_seconds: float = 60,
) -> Optional[str]:
    """
    Query Athena database and return the location of the output.

    Args:
        query: The SQL query to execute.
        client: The Athena boto3 client.
        db: The database to query.
        wg: The Athena work group name.
        timeout_seconds: Maximum time to wait for query completion.

    Returns:
        The S3 output location of the query results, or None on failure.
    """
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": db},
        WorkGroup=wg,
    )
    try:
        exec_id = response["QueryExecutionId"]
        deadline = time.time() + timeout_seconds
        state, reason, out_loc = "QUEUED", "", None
        while time.time() < deadline:
            info = client.get_query_execution(QueryExecutionId=exec_id)["QueryExecution"]
            state = info["Status"]["State"]
            reason = info["Status"].get("StateChangeReason", "")
            out_loc = info.get("ResultConfiguration", {}).get("OutputLocation")
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1.0)
        assert state == "SUCCEEDED", f"Athena state={state} reason={reason!r} exec_id={exec_id}"
        assert out_loc and out_loc.startswith("s3://"), f"unexpected output_location={out_loc!r}"
    except Exception as e:
        print(e)
        return None
    return out_loc

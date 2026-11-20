#!/usr/bin/env python3
"""Run flow, peak-min, and fault detectors for every surveyor in SurveyData."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROC_DIR = Path(__file__).resolve().parent
_ROOT = _PROC_DIR.parent
_PACKAGES = _ROOT.parents[2] / "packages"

for entry in (_PACKAGES, _ROOT):
    p = str(entry)
    if p not in sys.path:
        sys.path.insert(0, p)

from lib.Detector.FaultDetector import FaultDetector
from lib.Detector.FlowrateDetector import FlowRateDetector
from lib.Detector.PeakMinDetector import PeakMinDetector
from lib.SurveyorLookup import get_latest_customer_per_surveyor_unit


def _run_one_surveyor(
    customer_id: str,
    surveyor_unit_id: str,
    *,
    write_back: bool,
) -> None:
    for detector_cls in (FlowRateDetector, PeakMinDetector, FaultDetector):
        detector = detector_cls()
        detector.set_surveyor_unit(customer_id=customer_id, surveyor_unit_id=surveyor_unit_id)
        detector.load_data()
        detector.load_config()
        detector.run_detector(write_back=write_back)


def run_detector_fleet(*, write_back: bool = True, limit: int | None = None) -> int:
    """
    Run flow-rate, peak-min, and fault detectors for each surveyor unit.

    Returns the number of surveyors processed.
    """
    surveyor_lookup = get_latest_customer_per_surveyor_unit()
    if surveyor_lookup.empty:
        print("No surveyors in SurveyData.")
        return 0

    n = len(surveyor_lookup)
    if limit is not None:
        n = min(n, limit)
        surveyor_lookup = surveyor_lookup.iloc[:n]

    processed = 0
    for i in range(n):
        row = surveyor_lookup.iloc[i]
        customer_id = row["CustomerId"]
        surveyor_unit_id = row["SurveyorUnitId"]
        surveyor_unit = row.get("SurveyorUnit", "")
        customer_name = row.get("CustomerName", "")
        print(
            f"[{i + 1}/{n}] {customer_name} · {surveyor_unit} "
            f"(customer_id={customer_id}, surveyor_unit_id={surveyor_unit_id})"
        )
        try:
            _run_one_surveyor(customer_id, surveyor_unit_id, write_back=write_back)
            processed += 1
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            raise

    print(f"Fleet run complete — {processed} surveyor(s).")
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and config only; do not write detector tables.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N surveyors (for testing).",
    )
    args = parser.parse_args()
    run_detector_fleet(write_back=not args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
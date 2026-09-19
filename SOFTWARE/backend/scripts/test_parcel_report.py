from pathlib import Path
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from tests.test_parcel_report_api import ParcelReportApiTests
from tests.test_parcel_report_calc import (
    ChangeToneTests,
    ExecutiveSummaryTests,
    PercentChangeTests,
    RatioTests,
    TimelineTests,
    YearBoundsTests,
    YieldAggregationTests,
)


def main() -> None:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for case in (
        YearBoundsTests,
        PercentChangeTests,
        ChangeToneTests,
        YieldAggregationTests,
        RatioTests,
        TimelineTests,
        ExecutiveSummaryTests,
        ParcelReportApiTests,
    ):
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()

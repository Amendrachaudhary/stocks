"""
OpenQuant-FNO: Comprehensive Test Runner
Runs all unit and integration test suites.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_regex_parser import TestRegexParser
from tests.test_greeks_and_risk import TestQuantSuite
from tests.test_sqlite_blotter import TestSQLiteBlotter


def run_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestRegexParser))
    suite.addTests(loader.loadTestsFromTestCase(TestQuantSuite))
    suite.addTests(loader.loadTestsFromTestCase(TestSQLiteBlotter))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        sys.exit(1)
    print("\n[ALL TESTS PASSED SUCCESSFULLY]")


if __name__ == "__main__":
    run_suite()

"""Data validation tests per spec 13.4."""
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pages.admin import _run_data_validation


def test_no_duplicate_ids():
    df = pd.DataFrame({
        "UniqueID": [1, 2, 3],
        "IsShopper": [True] * 3,
        "IsSwitcher": [False] * 3,
        "IsRetained": [True] * 3,
        "IsNewToMarket": [False] * 3,
        "CurrentCompany": ["A"] * 3,
        "PreviousCompany": [None] * 3,
    })
    results = _run_data_validation(df)
    dup_check = next(r for r in results if "duplicate" in r["check"].lower())
    assert dup_check["status"] == "PASS"


def test_duplicate_ids_fail():
    df = pd.DataFrame({
        "UniqueID": [1, 1, 2],
        "IsShopper": [True] * 3,
        "IsSwitcher": [False] * 3,
        "IsRetained": [True] * 3,
        "IsNewToMarket": [False] * 3,
        "CurrentCompany": ["A"] * 3,
        "PreviousCompany": [None] * 3,
    })
    results = _run_data_validation(df)
    dup_check = next(r for r in results if "duplicate" in r["check"].lower())
    assert dup_check["status"] == "FAIL"


def test_empty_data():
    results = _run_data_validation(pd.DataFrame())
    assert len(results) == 1
    assert results[0]["status"] == "FAIL"

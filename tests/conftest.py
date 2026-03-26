"""
Shared pytest fixtures for IBT3 analytics tests.

All fixtures build minimal DataFrames that mirror the real data shape:
  - UniqueID, RenewalYearMonth (YYYYMM int), Product
  - CurrentCompany, PreviousCompany, IsSwitcher, IsNewToMarket
  - Boolean Q-code columns (Q2_Brand, Q27_Brand) for awareness tests
  - Q1 position columns for spontaneous awareness tests
"""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Base switching / flow fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def base_df():
    """
    Minimal DataFrame representing renewal respondents for Motor.

    Three insurers: Aviva, Admiral, Direct Line.
    Switchers go: 2 Aviva->Admiral, 1 Admiral->Direct Line, 1 Direct Line->Aviva.
    """
    rows = [
        # Stayers
        {"UniqueID": 1, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Aviva", "PreviousCompany": "Aviva",
         "IsSwitcher": False, "IsNewToMarket": False,
         "IsShopper": False},
        {"UniqueID": 2, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Aviva", "PreviousCompany": "Aviva",
         "IsSwitcher": False, "IsNewToMarket": False,
         "IsShopper": False},
        {"UniqueID": 3, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Admiral", "PreviousCompany": "Admiral",
         "IsSwitcher": False, "IsNewToMarket": False,
         "IsShopper": False},
        # Switchers
        {"UniqueID": 4, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Admiral", "PreviousCompany": "Aviva",
         "IsSwitcher": True, "IsNewToMarket": False,
         "IsShopper": True},
        {"UniqueID": 5, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Admiral", "PreviousCompany": "Aviva",
         "IsSwitcher": True, "IsNewToMarket": False,
         "IsShopper": True},
        {"UniqueID": 6, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Direct Line", "PreviousCompany": "Admiral",
         "IsSwitcher": True, "IsNewToMarket": False,
         "IsShopper": True},
        {"UniqueID": 7, "RenewalYearMonth": 202401, "Product": "Motor",
         "CurrentCompany": "Aviva", "PreviousCompany": "Direct Line",
         "IsSwitcher": True, "IsNewToMarket": False,
         "IsShopper": True},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def empty_df():
    """Completely empty DataFrame."""
    return pd.DataFrame()


@pytest.fixture
def none_df():
    """None (simulates missing data)."""
    return None


# ---------------------------------------------------------------------------
# Rates / rolling average fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def monthly_rates_df():
    """
    Month-level retention rates DataFrame, as produced by a groupby aggregation.
    Sorted by RenewalYearMonth ascending.
    """
    return pd.DataFrame({
        "RenewalYearMonth": [202401, 202402, 202403, 202404, 202405],
        "retention": [0.70, 0.72, 0.68, 0.74, 0.71],
        "n": [100, 110, 95, 120, 105],
    })


@pytest.fixture
def single_row_rates_df():
    """One-row DataFrame — edge case for rolling average."""
    return pd.DataFrame({
        "RenewalYearMonth": [202401],
        "retention": [0.70],
        "n": [100],
    })


# ---------------------------------------------------------------------------
# Awareness fixture (prompted Q2 boolean columns)
# ---------------------------------------------------------------------------

def _make_awareness_df(n_per_month: int = 50, months: list[int] | None = None) -> pd.DataFrame:
    """
    Build a wide-format DataFrame with Q2_ boolean columns for three brands.
    Denominator: respondents who answered the awareness question (have at least
    one True in Q2_ columns) — mirrors the real filtering logic.
    """
    if months is None:
        months = [202401, 202402]

    rng = np.random.default_rng(42)
    rows = []
    uid = 1
    for month in months:
        for _ in range(n_per_month):
            aviva = bool(rng.random() < 0.80)
            admiral = bool(rng.random() < 0.70)
            direct_line = bool(rng.random() < 0.60)
            # Ensure at least one True so respondent counts as answered
            if not any([aviva, admiral, direct_line]):
                aviva = True
            rows.append({
                "UniqueID": uid,
                "RenewalYearMonth": month,
                "Product": "Motor",
                "Q2_Aviva": aviva,
                "Q2_Admiral": admiral,
                "Q2_Direct Line": direct_line,
            })
            uid += 1

    df = pd.DataFrame(rows)
    # Cast boolean columns to proper bool dtype
    for col in ["Q2_Aviva", "Q2_Admiral", "Q2_Direct Line"]:
        df[col] = df[col].astype(bool)
    return df


@pytest.fixture
def awareness_df():
    """Multi-month awareness DataFrame with Q2 boolean columns."""
    return _make_awareness_df(n_per_month=50)


@pytest.fixture
def awareness_df_small():
    """Small awareness DataFrame — below SYSTEM_FLOOR_N=15 check threshold."""
    return _make_awareness_df(n_per_month=5)


# ---------------------------------------------------------------------------
# Spontaneous awareness fixture (Q1 position columns)
# ---------------------------------------------------------------------------

@pytest.fixture
def spontaneous_df():
    """
    DataFrame with Q1 position columns for two brands.
    Half the respondents mention Aviva at pos 1a; the other half mention Admiral.
    """
    rows = []
    for i in range(40):
        rows.append({
            "UniqueID": i,
            "RenewalYearMonth": 202401,
            "Product": "Motor",
            "Q1_pos1a": "Aviva" if i < 20 else "Admiral",
            "Q1_pos1b": None,
            "Q1_pos2a": "Admiral" if i < 20 else "Aviva",
            "Q1_pos2b": None,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# DuckDB temporary path fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    """
    Redirect DuckDB to a temporary file so tests never touch ~/.ibt3/cache.duckdb.
    """
    db_file = str(tmp_path / "test_cache.duckdb")
    monkeypatch.setenv("IBT3_DB_PATH", db_file)
    # Also patch the module-level variable in lib.db so already-imported
    # code picks up the new path.
    import lib.db as db_mod
    monkeypatch.setattr(db_mod, "_DB_PATH", db_file)
    return db_file

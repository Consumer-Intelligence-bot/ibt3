"""
Incomplete month detection and filtering for IBT3 trend charts.

Rationale:
  The most recent 1-2 months of data always have lower respondent counts
  because fieldwork is ongoing. Showing these months on trend charts causes
  misleading drops. This module provides utilities to detect and suppress
  incomplete months before rendering.

Completeness rule (dual threshold):
  A month is "complete" if BOTH conditions are met:
    1. count >= min_respondents  (absolute floor — protects against tiny samples)
    2. count >= 50% of the median month count  (relative — handles small insurers
       where the absolute floor alone would be too generous)

Applying the filter at the screen level (not inside analytics functions) keeps
the analytics pure and makes the suppression visible and testable in isolation.
"""
from __future__ import annotations

import pandas as pd


def _compute_completeness_mask(
    month_counts: pd.Series,
    min_respondents: int,
) -> pd.Series:
    """
    Return a boolean Series indexed by YYYYMM indicating which months are complete.

    Parameters
    ----------
    month_counts:
        Series mapping YYYYMM -> respondent count.
    min_respondents:
        Absolute floor for a month to be considered complete.
    """
    if month_counts.empty:
        return pd.Series(dtype=bool)

    median_count = month_counts.median()
    relative_floor = median_count * 0.5

    # Both conditions must be true (inclusive on boundary values)
    meets_absolute = month_counts >= min_respondents
    meets_relative = month_counts >= relative_floor

    return meets_absolute & meets_relative


def filter_complete_months(
    df: pd.DataFrame,
    min_respondents: int = 50,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Return a copy of *df* with incomplete months removed.

    A month is "complete" if:
      - respondent count >= ``min_respondents``, AND
      - respondent count >= 50% of the median month count

    The input DataFrame is never mutated.

    Parameters
    ----------
    df:
        Raw respondent-level DataFrame. Each row is one respondent.
    min_respondents:
        Absolute minimum count for a month to be retained.
    time_col:
        Name of the YYYYMM integer column. Default: "RenewalYearMonth".

    Returns
    -------
    pd.DataFrame
        Filtered copy. May be empty if all months are incomplete.
    """
    if df.empty or time_col not in df.columns:
        return df.copy()

    month_counts = df.groupby(time_col).size()
    complete_mask = _compute_completeness_mask(month_counts, min_respondents)
    complete_months = complete_mask[complete_mask].index

    return df[df[time_col].isin(complete_months)].copy()


def get_complete_month_range(
    df: pd.DataFrame,
    min_respondents: int = 50,
    time_col: str = "RenewalYearMonth",
) -> list[int]:
    """
    Return a sorted list of YYYYMM integer values for complete months.

    Parameters
    ----------
    df:
        Raw respondent-level DataFrame.
    min_respondents:
        Absolute minimum count for a month to be considered complete.
    time_col:
        Name of the YYYYMM integer column. Default: "RenewalYearMonth".

    Returns
    -------
    list[int]
        Sorted ascending list of complete YYYYMM integers. Empty if none.
    """
    if df.empty or time_col not in df.columns:
        return []

    month_counts = df.groupby(time_col).size()
    complete_mask = _compute_completeness_mask(month_counts, min_respondents)
    complete_months = complete_mask[complete_mask].index

    return sorted(complete_months.tolist())


def get_incomplete_months(
    df: pd.DataFrame,
    min_respondents: int = 50,
    time_col: str = "RenewalYearMonth",
) -> list[int]:
    """
    Return a sorted list of YYYYMM integer values for incomplete months.

    These are months that do NOT meet the completeness threshold and should
    be excluded from trend visualisations. The list is intended for use in
    user-facing warning captions, e.g.:
        "Note: 202403, 202404 excluded due to incomplete fieldwork."

    Parameters
    ----------
    df:
        Raw respondent-level DataFrame.
    min_respondents:
        Absolute minimum count for a month to be considered complete.
    time_col:
        Name of the YYYYMM integer column. Default: "RenewalYearMonth".

    Returns
    -------
    list[int]
        Sorted ascending list of incomplete YYYYMM integers. Empty if all complete.
    """
    if df.empty or time_col not in df.columns:
        return []

    month_counts = df.groupby(time_col).size()
    complete_mask = _compute_completeness_mask(month_counts, min_respondents)
    incomplete_months = complete_mask[~complete_mask].index

    return sorted(incomplete_months.tolist())

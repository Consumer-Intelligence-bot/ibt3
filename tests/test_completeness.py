"""
Unit tests for incomplete month detection and filtering.

Covers:
  - filter_complete_months  (lib/analytics/completeness.py)
  - get_complete_month_range (lib/analytics/completeness.py)
  - get_incomplete_months   (lib/analytics/completeness.py)

TDD methodology: tests written BEFORE implementation.
Logic under test:
  - A month is "complete" if count >= min_respondents AND >= 50% of median count
  - The dual threshold handles both small-insurer and market-level data
  - Trailing months with incomplete fieldwork are naturally caught by low counts
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helper to build a minimal DataFrame with RenewalYearMonth + row-per-respondent
# ---------------------------------------------------------------------------

def _make_df(month_counts: dict[int, int]) -> pd.DataFrame:
    """
    Build a DataFrame where each key is a YYYYMM month and the value is the
    number of respondents in that month.
    """
    rows = []
    uid = 1
    for month, n in month_counts.items():
        for _ in range(n):
            rows.append({"UniqueID": uid, "RenewalYearMonth": month, "Product": "Motor"})
            uid += 1
    if not rows:
        return pd.DataFrame(columns=["UniqueID", "RenewalYearMonth", "Product"])
    return pd.DataFrame(rows)


# ===========================================================================
# 1. filter_complete_months
# ===========================================================================

class TestFilterCompleteMonths:
    """lib/analytics/completeness.py :: filter_complete_months"""

    def test_all_complete_months_returned(self):
        """All months have 100 respondents — all should be returned."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 100})
        result = filter_complete_months(df)
        assert len(result) == 300
        assert set(result["RenewalYearMonth"].unique()) == {202401, 202402, 202403}

    def test_last_month_too_few_removed(self):
        """Last month has only 10 respondents (well below 50) — should be removed."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 10})
        result = filter_complete_months(df)
        assert 202403 not in result["RenewalYearMonth"].values
        assert set(result["RenewalYearMonth"].unique()) == {202401, 202402}

    def test_two_trailing_months_removed(self):
        """Last two months have low counts — both should be removed."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 20, 202404: 5})
        result = filter_complete_months(df)
        assert set(result["RenewalYearMonth"].unique()) == {202401, 202402}

    def test_single_complete_month_returned(self):
        """Single month with 100 respondents — no median comparison issue, returned."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100})
        result = filter_complete_months(df)
        assert len(result) == 100
        assert list(result["RenewalYearMonth"].unique()) == [202401]

    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame input — returns empty DataFrame."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({})
        result = filter_complete_months(df)
        assert len(result) == 0
        assert isinstance(result, pd.DataFrame)

    def test_all_months_below_threshold_returns_empty(self):
        """All months have fewer respondents than min_respondents — returns empty."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 10, 202402: 15, 202403: 8})
        result = filter_complete_months(df, min_respondents=50)
        assert len(result) == 0

    def test_custom_min_respondents_threshold(self):
        """Custom min_respondents=20: months with >=20 respondents kept."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 25})
        # Median is 100; 50% of median = 50. Month 202403 has 25 < 50, so removed
        # even though 25 >= 20.
        result = filter_complete_months(df, min_respondents=20)
        assert 202403 not in result["RenewalYearMonth"].values

    def test_custom_min_respondents_below_fifty_percent_median(self):
        """
        Month passes the absolute threshold but fails the 50%-of-median check.
        E.g. median=100, month has 40 — passes min_respondents=30 but < 50.
        """
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 40})
        result = filter_complete_months(df, min_respondents=30)
        # 40 >= 30 (absolute ok) but 40 < 50% of median(100) = 50 → removed
        assert 202403 not in result["RenewalYearMonth"].values

    def test_does_not_mutate_input_dataframe(self):
        """filter_complete_months must not mutate the original DataFrame."""
        from lib.analytics.completeness import filter_complete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 10})
        original_len = len(df)
        original_months = set(df["RenewalYearMonth"].unique())
        filter_complete_months(df)
        # Input must be unchanged
        assert len(df) == original_len
        assert set(df["RenewalYearMonth"].unique()) == original_months

    def test_custom_time_col(self):
        """Works with a custom time column name."""
        from lib.analytics.completeness import filter_complete_months
        df = pd.DataFrame({
            "UniqueID": range(210),
            "SurveyYearMonth": [202401] * 100 + [202402] * 100 + [202403] * 10,
            "Product": "Motor",
        })
        result = filter_complete_months(df, time_col="SurveyYearMonth")
        assert 202403 not in result["SurveyYearMonth"].values

    def test_month_at_exactly_fifty_percent_median_is_kept(self):
        """
        A month at exactly 50% of the median count should be kept (inclusive boundary).
        """
        from lib.analytics.completeness import filter_complete_months
        # Median = 100 (months 202401 and 202402 each 100)
        # Month 202403 = 50 which is exactly 50% of 100
        df = _make_df({202401: 100, 202402: 100, 202403: 50})
        result = filter_complete_months(df)
        assert 202403 in result["RenewalYearMonth"].values

    def test_month_just_below_fifty_percent_median_is_removed(self):
        """A month at 49% of the median count should be removed."""
        from lib.analytics.completeness import filter_complete_months
        # Median = 100; 49 < 50 (50% of 100)
        df = _make_df({202401: 100, 202402: 100, 202403: 49})
        result = filter_complete_months(df)
        assert 202403 not in result["RenewalYearMonth"].values


# ===========================================================================
# 2. get_complete_month_range
# ===========================================================================

class TestGetCompleteMonthRange:
    """lib/analytics/completeness.py :: get_complete_month_range"""

    def test_returns_sorted_list_of_yyyymm_integers(self):
        """Returns a sorted list of integer YYYYMM values."""
        from lib.analytics.completeness import get_complete_month_range
        df = _make_df({202403: 100, 202401: 100, 202402: 100})
        result = get_complete_month_range(df)
        assert result == [202401, 202402, 202403]

    def test_excludes_incomplete_months(self):
        """Incomplete months are not included in the range."""
        from lib.analytics.completeness import get_complete_month_range
        df = _make_df({202401: 100, 202402: 100, 202403: 5})
        result = get_complete_month_range(df)
        assert result == [202401, 202402]
        assert 202403 not in result

    def test_empty_dataframe_returns_empty_list(self):
        """Empty DataFrame returns empty list (not None, not error)."""
        from lib.analytics.completeness import get_complete_month_range
        df = _make_df({})
        result = get_complete_month_range(df)
        assert result == []

    def test_single_month_returns_single_element_list(self):
        """Single month DataFrame returns a one-element list."""
        from lib.analytics.completeness import get_complete_month_range
        df = _make_df({202401: 100})
        result = get_complete_month_range(df)
        assert result == [202401]

    def test_all_incomplete_returns_empty_list(self):
        """When all months are below threshold, returns empty list."""
        from lib.analytics.completeness import get_complete_month_range
        df = _make_df({202401: 5, 202402: 8})
        result = get_complete_month_range(df)
        assert result == []


# ===========================================================================
# 3. get_incomplete_months
# ===========================================================================

class TestGetIncompleteMonths:
    """lib/analytics/completeness.py :: get_incomplete_months"""

    def test_returns_only_incomplete_months(self):
        """Returns only months that do NOT meet the completeness threshold."""
        from lib.analytics.completeness import get_incomplete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 10})
        result = get_incomplete_months(df)
        assert result == [202403]

    def test_all_complete_returns_empty_list(self):
        """When all months are complete, returns empty list."""
        from lib.analytics.completeness import get_incomplete_months
        df = _make_df({202401: 100, 202402: 100, 202403: 100})
        result = get_incomplete_months(df)
        assert result == []

    def test_empty_dataframe_returns_empty_list(self):
        """Empty DataFrame returns empty list."""
        from lib.analytics.completeness import get_incomplete_months
        df = _make_df({})
        result = get_incomplete_months(df)
        assert result == []

    def test_multiple_incomplete_months_sorted(self):
        """Multiple incomplete months are returned sorted ascending."""
        from lib.analytics.completeness import get_incomplete_months
        df = _make_df({202401: 100, 202402: 5, 202403: 100, 202404: 8})
        result = get_incomplete_months(df)
        assert result == [202402, 202404]

    def test_all_incomplete_returns_all_months(self):
        """When all months are below threshold, returns all month values."""
        from lib.analytics.completeness import get_incomplete_months
        df = _make_df({202401: 5, 202402: 8})
        result = get_incomplete_months(df)
        assert result == [202401, 202402]

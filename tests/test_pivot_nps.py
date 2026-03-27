"""
Tests for NPS/Scale question pivoting in lib/analytics/pivot.py.

TDD: Tests written first. Q47 Answer column has mixed formats:
  - Pure numeric: "1", "2", "3", "4", "5"
  - Text labels: "1 – Completely dissatisfied", "5 – Completely satisfied"
The Scale column always has the clean numeric value.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.analytics.pivot import pivot_questions_to_wide


@pytest.fixture
def q47_mixed_answers():
    """EAV data with mixed Answer formats, clean Scale column."""
    return pd.DataFrame({
        "UniqueID": ["U1", "U2", "U3", "U4", "U5"],
        "QuestionNumber": ["Q47"] * 5,
        "Answer": [
            "5",
            "5 – Completely satisfied",
            "3 – Neither satisfied nor dissatisfied",
            "1 – Completely dissatisfied",
            "4",
        ],
        "Scale": [5, 5, 3, 1, 4],
        "Subject": [None] * 5,
        "Ranking": [None] * 5,
    })


@pytest.fixture
def q48_mixed_answers():
    """Q48 NPS with text labels in Answer, clean Scale."""
    return pd.DataFrame({
        "UniqueID": ["U1", "U2", "U3"],
        "QuestionNumber": ["Q48"] * 3,
        "Answer": ["9", "7 – Would recommend", "3"],
        "Scale": [9, 7, 3],
        "Subject": [None] * 3,
        "Ranking": [None] * 3,
    })


@pytest.fixture
def nps_no_scale():
    """NPS data without Scale column (pure numeric Answer)."""
    return pd.DataFrame({
        "UniqueID": ["U1", "U2", "U3"],
        "QuestionNumber": ["Q47"] * 3,
        "Answer": ["4", "5", "2"],
        "Subject": [None] * 3,
        "Ranking": [None] * 3,
    })


class TestPivotNpsWithScale:
    """NPS pivot should use Scale when Answer contains text labels."""

    def test_all_respondents_preserved(self, q47_mixed_answers):
        result = pivot_questions_to_wide(q47_mixed_answers)
        assert "Q47" in result.columns
        non_null = result["Q47"].dropna()
        assert len(non_null) == 5, f"Expected 5 Q47 values, got {len(non_null)}"

    def test_values_from_scale(self, q47_mixed_answers):
        result = pivot_questions_to_wide(q47_mixed_answers)
        vals = sorted(result["Q47"].dropna().unique().tolist())
        assert vals == [1.0, 3.0, 4.0, 5.0]

    def test_text_answer_respondent_not_dropped(self, q47_mixed_answers):
        """U2 has Answer='5 – Completely satisfied' — must not be dropped."""
        result = pivot_questions_to_wide(q47_mixed_answers)
        assert result.loc["U2", "Q47"] == 5.0

    def test_q48_also_uses_scale(self, q48_mixed_answers):
        result = pivot_questions_to_wide(q48_mixed_answers)
        assert "Q48" in result.columns
        assert result.loc["U2", "Q48"] == 7.0  # "7 – Would recommend" -> Scale=7

    def test_full_1_5_range_present(self, q47_mixed_answers):
        """With Scale, all 1-5 values should be capturable."""
        result = pivot_questions_to_wide(q47_mixed_answers)
        vals = set(result["Q47"].dropna().unique())
        assert 1.0 in vals
        assert 3.0 in vals
        assert 5.0 in vals


class TestPivotNpsWithoutScale:
    """NPS pivot falls back to Answer when no Scale column."""

    def test_numeric_answer_still_works(self, nps_no_scale):
        result = pivot_questions_to_wide(nps_no_scale)
        assert "Q47" in result.columns
        assert len(result["Q47"].dropna()) == 3

    def test_values_correct(self, nps_no_scale):
        result = pivot_questions_to_wide(nps_no_scale)
        vals = sorted(result["Q47"].dropna().unique().tolist())
        assert vals == [2.0, 4.0, 5.0]

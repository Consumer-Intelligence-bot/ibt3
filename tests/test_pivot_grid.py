"""
Tests for grid question pivoting (Q46, Q53) in lib/analytics/pivot.py.

TDD: Tests written first to define expected behaviour when Answer column
contains text labels (e.g. "Agree") and Scale column has numeric values.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.analytics.pivot import pivot_questions_to_wide


@pytest.fixture
def q46_eav_with_scale():
    """EAV data matching real Power BI structure: Answer=text, Scale=numeric."""
    return pd.DataFrame({
        "UniqueID": ["U1", "U1", "U1", "U2", "U2", "U2", "U3", "U3", "U3"],
        "QuestionNumber": ["Q46"] * 9,
        "Answer": [
            "Agree", "Strongly agree", "Disagree",
            "Strongly agree", "Agree", "Agree",
            "Disagree", "Strongly disagree", "Agree",
        ],
        "Scale": [4, 5, 2, 5, 4, 4, 2, 1, 4],
        "Subject": [
            "My insurer provides me fair value",
            "My insurer is transparent",
            "My insurer acts in my interest",
        ] * 3,
        "Ranking": [97, 98, 99] * 3,
    })


@pytest.fixture
def q46_eav_numeric_answer():
    """EAV data where Answer IS numeric (no Scale needed)."""
    return pd.DataFrame({
        "UniqueID": ["U1", "U1", "U2", "U2"],
        "QuestionNumber": ["Q46"] * 4,
        "Answer": ["4", "5", "3", "4"],
        "Subject": ["Fair value", "Transparent"] * 2,
        "Ranking": [97, 98] * 2,
    })


@pytest.fixture
def q53_eav_with_scale():
    """Q53 claims grid data with text Answer and numeric Scale."""
    return pd.DataFrame({
        "UniqueID": ["U1", "U1", "U2", "U2"],
        "QuestionNumber": ["Q53"] * 4,
        "Answer": ["Satisfied", "Dissatisfied", "Satisfied", "Satisfied"],
        "Scale": [4, 2, 4, 4],
        "Subject": ["Speed of claim", "Communication"] * 2,
        "Ranking": [97, 98] * 2,
    })


class TestPivotGridWithScale:
    """Grid pivot should use Scale column when Answer is non-numeric."""

    def test_q46_columns_created_from_text_answers(self, q46_eav_with_scale):
        result = pivot_questions_to_wide(q46_eav_with_scale)
        q46_cols = [c for c in result.columns if c.startswith("Q46_")]
        assert len(q46_cols) == 3, f"Expected 3 Q46 columns, got {q46_cols}"

    def test_q46_subject_names_in_columns(self, q46_eav_with_scale):
        result = pivot_questions_to_wide(q46_eav_with_scale)
        cols = set(result.columns)
        assert "Q46_My insurer provides me fair value" in cols
        assert "Q46_My insurer is transparent" in cols
        assert "Q46_My insurer acts in my interest" in cols

    def test_q46_values_from_scale_not_answer(self, q46_eav_with_scale):
        result = pivot_questions_to_wide(q46_eav_with_scale)
        # U1 answered "Agree" (Scale=4) for fair value
        val = result.loc["U1", "Q46_My insurer provides me fair value"]
        assert val == 4.0

    def test_q46_numeric_answer_still_works(self, q46_eav_numeric_answer):
        """When Answer is already numeric, it should still work."""
        result = pivot_questions_to_wide(q46_eav_numeric_answer)
        q46_cols = [c for c in result.columns if c.startswith("Q46_")]
        assert len(q46_cols) == 2

    def test_q53_also_uses_scale(self, q53_eav_with_scale):
        result = pivot_questions_to_wide(q53_eav_with_scale)
        q53_cols = [c for c in result.columns if c.startswith("Q53_")]
        assert len(q53_cols) == 2
        val = result.loc["U1", "Q53_Speed of claim"]
        assert val == 4.0


class TestPivotGridWithoutScale:
    """Grid pivot handles missing Scale column gracefully."""

    def test_no_scale_column_uses_answer(self):
        """When there is no Scale column at all, fall back to Answer."""
        df = pd.DataFrame({
            "UniqueID": ["U1", "U1"],
            "QuestionNumber": ["Q46", "Q46"],
            "Answer": ["4", "5"],
            "Subject": ["Fair value", "Transparent"],
            "Ranking": [97, 98],
        })
        result = pivot_questions_to_wide(df)
        q46_cols = [c for c in result.columns if c.startswith("Q46_")]
        assert len(q46_cols) == 2

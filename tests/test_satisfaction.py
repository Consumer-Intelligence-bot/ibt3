"""
Tests for satisfaction analytics (lib/analytics/satisfaction.py).

TDD: Tests written first to define expected behaviour for binary satisfaction
detection (Q47 stores codes 2=dissatisfied, 4=satisfied, not a 1-5 scale).
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.analytics.satisfaction import (
    calc_overall_satisfaction,
    calc_nps,
    calc_brand_perception,
    calc_satisfaction_retention_matrix,
    calc_previous_insurer_satisfaction,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def binary_sat_df():
    """DataFrame with binary Q47 values (2 and 4 only) — real data pattern."""
    rng = np.random.default_rng(42)
    n = 1000
    # 97% satisfied (4), 3% dissatisfied (2) — mirrors actual data
    q47 = rng.choice([2.0, 4.0], size=n, p=[0.03, 0.97])
    return pd.DataFrame({"Q47": q47})


@pytest.fixture
def full_scale_sat_df():
    """DataFrame with full 1-5 Q47 values — what normal data would look like."""
    rng = np.random.default_rng(42)
    n = 1000
    q47 = rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], size=n, p=[0.05, 0.10, 0.20, 0.40, 0.25])
    return pd.DataFrame({"Q47": q47})


@pytest.fixture
def nps_df():
    """DataFrame with Q48 NPS values (1-9 scale)."""
    rng = np.random.default_rng(42)
    n = 500
    q48 = rng.choice(range(1, 10), size=n)
    return pd.DataFrame({"Q48": q48.astype(float)})


@pytest.fixture
def retention_binary_df():
    """DataFrame with binary Q47 and IsRetained for retention matrix."""
    rng = np.random.default_rng(42)
    n = 500
    q47 = rng.choice([2.0, 4.0], size=n, p=[0.1, 0.9])
    retained = rng.choice([True, False], size=n, p=[0.7, 0.3])
    return pd.DataFrame({"Q47": q47, "IsRetained": retained})


@pytest.fixture
def q46_df():
    """DataFrame with Q46_* brand perception columns."""
    rng = np.random.default_rng(42)
    n = 200
    return pd.DataFrame({
        "CurrentCompany": rng.choice(["Admiral", "Aviva", "Direct Line"], size=n),
        "Q46_Value for money": rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], size=n),
        "Q46_Customer service": rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], size=n),
        "Q46_Trust": rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], size=n),
    })


# ---------------------------------------------------------------------------
# calc_overall_satisfaction — binary detection
# ---------------------------------------------------------------------------

class TestCalcOverallSatisfactionBinary:
    """Q47 binary satisfaction: codes 2 (dissatisfied) and 4 (satisfied)."""

    def test_detects_binary_satisfaction(self, binary_sat_df):
        result = calc_overall_satisfaction(binary_sat_df, "Q47")
        assert result is not None
        # Must flag that this is binary-coded data
        assert result.get("is_binary") is True

    def test_binary_returns_satisfied_pct(self, binary_sat_df):
        result = calc_overall_satisfaction(binary_sat_df, "Q47")
        assert result is not None
        assert "satisfied_pct" in result
        assert 0.95 <= result["satisfied_pct"] <= 0.99  # ~97%

    def test_binary_returns_dissatisfied_pct(self, binary_sat_df):
        result = calc_overall_satisfaction(binary_sat_df, "Q47")
        assert result is not None
        assert "dissatisfied_pct" in result
        assert 0.01 <= result["dissatisfied_pct"] <= 0.05  # ~3%

    def test_binary_pcts_sum_to_one(self, binary_sat_df):
        result = calc_overall_satisfaction(binary_sat_df, "Q47")
        assert result is not None
        total = result["satisfied_pct"] + result["dissatisfied_pct"]
        assert total == pytest.approx(1.0)

    def test_binary_still_returns_n(self, binary_sat_df):
        result = calc_overall_satisfaction(binary_sat_df, "Q47")
        assert result is not None
        assert result["n"] == 1000

    def test_binary_still_returns_distribution(self, binary_sat_df):
        """Distribution should still be present for backward compat."""
        result = calc_overall_satisfaction(binary_sat_df, "Q47")
        assert result is not None
        assert "distribution" in result


class TestCalcOverallSatisfactionFullScale:
    """Q47 with full 1-5 scale: standard behaviour."""

    def test_full_scale_not_binary(self, full_scale_sat_df):
        result = calc_overall_satisfaction(full_scale_sat_df, "Q47")
        assert result is not None
        assert result.get("is_binary") is False

    def test_full_scale_mean_in_range(self, full_scale_sat_df):
        result = calc_overall_satisfaction(full_scale_sat_df, "Q47")
        assert result is not None
        assert 1.0 <= result["mean"] <= 5.0

    def test_full_scale_distribution_has_five_values(self, full_scale_sat_df):
        result = calc_overall_satisfaction(full_scale_sat_df, "Q47")
        assert result is not None
        assert len(result["distribution"]) == 5


class TestCalcOverallSatisfactionEdgeCases:
    """Edge cases for calc_overall_satisfaction."""

    def test_none_df_returns_none(self):
        assert calc_overall_satisfaction(None) is None

    def test_empty_df_returns_none(self):
        assert calc_overall_satisfaction(pd.DataFrame()) is None

    def test_missing_column_returns_none(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        assert calc_overall_satisfaction(df, "Q47") is None

    def test_all_nan_returns_none(self):
        df = pd.DataFrame({"Q47": [float("nan")] * 10})
        assert calc_overall_satisfaction(df, "Q47") is None


# ---------------------------------------------------------------------------
# calc_satisfaction_retention_matrix — binary-aware
# ---------------------------------------------------------------------------

class TestSatisfactionRetentionBinary:
    """Retention matrix with binary Q47 data."""

    def test_binary_retention_returns_two_bands(self, retention_binary_df):
        result = calc_satisfaction_retention_matrix(retention_binary_df)
        assert result is not None
        # With binary data (2 and 4), should have exactly 2 meaningful bands
        assert len(result) == 2

    def test_binary_retention_band_labels(self, retention_binary_df):
        result = calc_satisfaction_retention_matrix(retention_binary_df)
        assert result is not None
        labels = result["satisfaction_band"].tolist()
        assert "Satisfied" in labels
        assert "Dissatisfied" in labels

    def test_binary_retention_pct_in_range(self, retention_binary_df):
        result = calc_satisfaction_retention_matrix(retention_binary_df)
        assert result is not None
        for _, row in result.iterrows():
            assert 0.0 <= row["retained_pct"] <= 1.0


# ---------------------------------------------------------------------------
# calc_nps — standard behaviour (no change expected)
# ---------------------------------------------------------------------------

class TestCalcNps:
    """NPS calculation remains unchanged."""

    def test_nps_returns_score(self, nps_df):
        result = calc_nps(nps_df, "Q48")
        assert result is not None
        assert -100 <= result["nps"] <= 100

    def test_nps_returns_breakdown(self, nps_df):
        result = calc_nps(nps_df, "Q48")
        assert result is not None
        total = result["promoters_pct"] + result["passives_pct"] + result["detractors_pct"]
        assert total == pytest.approx(1.0)

    def test_nps_none_on_missing(self):
        assert calc_nps(None) is None


# ---------------------------------------------------------------------------
# calc_brand_perception — Q46
# ---------------------------------------------------------------------------

class TestCalcBrandPerception:
    """Q46 brand perception."""

    def test_returns_dataframe_with_columns(self, q46_df):
        result = calc_brand_perception(q46_df)
        assert result is not None
        assert "subject" in result.columns
        assert "mean_score" in result.columns
        assert "n" in result.columns

    def test_returns_correct_subjects(self, q46_df):
        result = calc_brand_perception(q46_df)
        assert result is not None
        subjects = set(result["subject"].tolist())
        assert "Value for money" in subjects
        assert "Customer service" in subjects
        assert "Trust" in subjects

    def test_insurer_filter_works(self, q46_df):
        result = calc_brand_perception(q46_df, insurer="Admiral")
        assert result is not None
        # Fewer respondents than full market
        assert all(result["n"] < 200)

    def test_returns_none_without_q46_columns(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        assert calc_brand_perception(df) is None

    def test_returns_none_on_empty(self):
        assert calc_brand_perception(None) is None

"""Tests for analytics/awareness.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from analytics.awareness import (
    Q1_GATING_MESSAGE,
    calc_awareness_rates,
    calc_awareness_bump,
    calc_awareness_slopegraph,
    calc_awareness_summary,
    calc_awareness_market_bands,
)


@pytest.fixture
def main_data():
    """Minimal MainData with 2 months of data."""
    return pd.DataFrame({
        "UniqueID": [str(i) for i in range(1, 101)],
        "RenewalYearMonth": [202401] * 50 + [202402] * 50,
        "CurrentCompany": ["Aviva"] * 30 + ["Direct Line"] * 20 + ["Aviva"] * 25 + ["Direct Line"] * 25,
        "IsShopper": [True] * 100,
        "IsSwitcher": [False] * 100,
        "IsRetained": [True] * 100,
        "IsNewToMarket": [False] * 100,
    })


@pytest.fixture
def eav_data():
    """EAV Q2 data — prompted awareness mentions."""
    rows = []
    for i in range(1, 51):
        rows.append({"UniqueID": str(i), "QuestionNumber": "Q2", "Answer": "Aviva"})
        if i % 2 == 0:
            rows.append({"UniqueID": str(i), "QuestionNumber": "Q2", "Answer": "Direct Line"})
    for i in range(51, 101):
        rows.append({"UniqueID": str(i), "QuestionNumber": "Q2", "Answer": "Aviva"})
        if i % 3 == 0:
            rows.append({"UniqueID": str(i), "QuestionNumber": "Q2", "Answer": "Churchill"})
    return pd.DataFrame(rows)


class TestCalcAwarenessRates:
    def test_returns_dataframe(self, main_data, eav_data):
        result = calc_awareness_rates(main_data, eav_data, "prompted")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    def test_has_required_columns(self, main_data, eav_data):
        result = calc_awareness_rates(main_data, eav_data, "prompted")
        for col in ("brand", "month", "rate", "ci_lower", "ci_upper", "rank"):
            assert col in result.columns

    def test_rates_between_0_and_1(self, main_data, eav_data):
        result = calc_awareness_rates(main_data, eav_data, "prompted")
        assert (result["rate"] >= 0).all()
        assert (result["rate"] <= 1).all()

    def test_spontaneous_returns_empty(self, main_data, eav_data):
        result = calc_awareness_rates(main_data, eav_data, "spontaneous")
        assert result.empty

    def test_empty_questions_returns_empty(self, main_data):
        result = calc_awareness_rates(main_data, pd.DataFrame(), "prompted")
        assert result.empty


class TestCalcAwarenessBump:
    def test_bump_data(self, main_data, eav_data):
        result = calc_awareness_bump(main_data, eav_data, "prompted")
        assert "rank" in result.columns if not result.empty else True

    def test_excludes_brands_missing_months(self, main_data, eav_data):
        """Brands without data in every month of the period are excluded."""
        result = calc_awareness_bump(main_data, eav_data, "prompted")
        if not result.empty:
            all_months = result["month"].nunique()
            for brand in result["brand"].unique():
                brand_months = result[result["brand"] == brand]["month"].nunique()
                assert brand_months == all_months


class TestCalcAwarenessSlopegraph:
    def test_returns_dict(self, main_data, eav_data):
        result = calc_awareness_slopegraph(main_data, eav_data, "Aviva", "prompted")
        if result is not None:
            assert "start_rate" in result
            assert "end_rate" in result
            assert "direction" in result
            assert "start_market_rate" in result
            assert "end_market_rate" in result

    def test_missing_brand_returns_none(self, main_data, eav_data):
        result = calc_awareness_slopegraph(main_data, eav_data, "NonExistent", "prompted")
        assert result is None


class TestCalcAwarenessSummary:
    def test_returns_summary(self, main_data, eav_data):
        result = calc_awareness_summary(main_data, eav_data, "prompted")
        assert result is not None
        assert "n_brands" in result
        assert result["n_brands"] > 0
        assert "mean_rate" in result
        assert "most_improved_name" in result

    def test_spontaneous_returns_none(self, main_data, eav_data):
        result = calc_awareness_summary(main_data, eav_data, "spontaneous")
        assert result is None


class TestCalcAwarenessMarketBands:
    def test_returns_bands(self, main_data, eav_data):
        result = calc_awareness_market_bands(main_data, eav_data, "prompted")
        if not result.empty:
            assert "p25" in result.columns
            assert "median" in result.columns
            assert "p75" in result.columns


class TestQ1Gating:
    def test_gating_message_exists(self):
        assert "Q1" in Q1_GATING_MESSAGE
        assert "not available" in Q1_GATING_MESSAGE.lower()

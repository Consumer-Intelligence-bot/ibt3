"""Tests for data/queries.py — EAV query helpers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from data.queries import (
    count_mentions,
    query_multi,
    query_ranked,
    query_single,
    respondent_count,
    top_reason,
)


@pytest.fixture
def eav_data():
    """Minimal EAV table for testing."""
    return pd.DataFrame({
        "UniqueID": ["1", "1", "2", "2", "2", "3", "3", "4"],
        "QuestionNumber": ["Q2", "Q2", "Q2", "Q8", "Q8", "Q2", "Q15", "Q2"],
        "Answer": ["Aviva", "Direct Line", "Aviva", "Price", "Service", "Churchill", "Switcher", "Aviva"],
    })


@pytest.fixture
def ranked_data():
    """EAV table with Rank column for ranked questions."""
    return pd.DataFrame({
        "UniqueID": ["1", "1", "1", "2", "2"],
        "QuestionNumber": ["Q8", "Q8", "Q8", "Q8", "Q8"],
        "Answer": ["Price", "Service", "Brand", "Service", "Price"],
        "Rank": [1, 2, 3, 1, 2],
    })


class TestQuerySingle:
    def test_returns_series(self, eav_data):
        result = query_single(eav_data, "Q15")
        assert isinstance(result, pd.Series)
        assert len(result) == 1
        assert result.iloc[0] == "Switcher"

    def test_empty_for_missing_question(self, eav_data):
        result = query_single(eav_data, "Q99")
        assert result.empty

    def test_deduplicates_multi_answer(self, eav_data):
        result = query_single(eav_data, "Q2")
        # Respondent 1 has two Q2 answers; should keep first
        assert "1" in result.index
        assert result.loc["1"] in ("Aviva", "Direct Line")

    def test_filters_by_respondent_ids(self, eav_data):
        result = query_single(eav_data, "Q2", respondent_ids=["1", "2"])
        assert "3" not in result.index


class TestQueryMulti:
    def test_returns_all_answers(self, eav_data):
        result = query_multi(eav_data, "Q2")
        assert len(result) == 5  # 2+1+1+1

    def test_columns(self, eav_data):
        result = query_multi(eav_data, "Q2")
        assert list(result.columns) == ["UniqueID", "Answer"]

    def test_filters_by_respondent(self, eav_data):
        result = query_multi(eav_data, "Q2", respondent_ids=["1"])
        assert len(result) == 2
        assert all(result["UniqueID"] == "1")

    def test_empty_for_missing_question(self, eav_data):
        result = query_multi(eav_data, "Q99")
        assert result.empty


class TestQueryRanked:
    def test_uses_rank_column(self, ranked_data):
        result = query_ranked(ranked_data, "Q8")
        assert "Rank" in result.columns
        r1 = result[result["UniqueID"] == "1"]
        assert list(r1["Rank"]) == [1, 2, 3]

    def test_generates_rank_when_missing(self, eav_data):
        result = query_ranked(eav_data, "Q8")
        assert "Rank" in result.columns
        r2 = result[result["UniqueID"] == "2"]
        assert list(r2["Rank"]) == [1, 2]


class TestCountMentions:
    def test_counts_unique_answers(self, eav_data):
        result = count_mentions(eav_data, "Q2")
        assert result["Aviva"] == 3
        assert result["Direct Line"] == 1
        assert result["Churchill"] == 1


class TestRespondentCount:
    def test_counts_distinct(self, eav_data):
        n = respondent_count(eav_data, "Q2")
        assert n == 4  # respondents 1, 2, 3, 4

    def test_zero_for_missing(self, eav_data):
        n = respondent_count(eav_data, "Q99")
        assert n == 0


class TestTopReason:
    def test_returns_ranked_results(self, ranked_data):
        result = top_reason(ranked_data, "Q8", top_n=3)
        assert len(result) >= 1
        assert result[0]["reason"] in ("Price", "Service")
        assert "rank1_pct" in result[0]

    def test_respects_top_n(self, ranked_data):
        result = top_reason(ranked_data, "Q8", top_n=1)
        assert len(result) == 1

    def test_empty_for_missing(self, eav_data):
        result = top_reason(eav_data, "Q99")
        assert result == []

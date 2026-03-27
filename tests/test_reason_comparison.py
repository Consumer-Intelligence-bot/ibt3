"""
TDD tests: calc_reason_comparison — market lookup completeness.

Spec: When an insurer's top-N reasons include a reason that doesn't appear
in the market's own top-N, the market percentage must still be populated
(possibly <1% or a small value) rather than 0.

Root cause being tested: calc_reason_comparison called calc_reason_ranking
with top_n=5 for both insurer and market. If insurer reason #3 is ranked
#12 market-wide, the market lookup returned 0 (defaulting via dict.get),
causing the table to display 0% and the index to be None.

Fix: market lookup should use a large top_n (≥20) so rare-but-real reasons
are captured for the market side of the comparison.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_ranked_df(n_respondents: int = 300) -> pd.DataFrame:
    """
    Build a minimal wide-format DataFrame with Q19 ranked columns.

    Scenario (designed to reproduce spec 6c bug):
      - 300 respondents total, 30 from "First Central".
      - Market top 8 reasons are cycled through the 270 non-FC respondents.
        "I didn't have time" is reason #8, appearing in only 12 out of 270
        non-FC respondents (~4.4% market rate) — ranks 8th, outside top-5.
      - First Central: 15 of 30 respondents cite "I didn't have time" (50%).

    This ensures "I didn't have time" ranks outside the market top-5 but
    is dominant for First Central. With market top_n=5, it won't be in the
    market lookup, causing market_pct=0. With top_n=20 it will be found.
    """
    rows = []
    uid = 1

    # 8 distinct reasons. Reasons 0-4 dominate market (each ~54 mentions, 20%+).
    # Reasons 5-7 are rare: ~18 mentions each (~6.7%), and reason 7 is even rarer.
    market_reasons = [
        "Price was too high",            # rank 1 (most common)
        "Already had a good deal",        # rank 2
        "Couldn't be bothered",           # rank 3
        "Happy with current insurer",     # rank 4
        "Too complicated to switch",      # rank 5 — last of the top-5 market
        "Didn't have enough information", # rank 6 — outside top-5
        "Spouse/partner handles it",      # rank 7 — outside top-5
        "I didn't have time",             # rank 8 — RARE, outside top-5 (FC over-indexes)
    ]

    fc_top_reason = "I didn't have time"

    for i in range(n_respondents):
        uid_val = uid
        if i < 30:
            # First Central respondents: 50% have FC top reason at rank 1
            company = "First Central"
            if i < 15:
                rank1 = fc_top_reason
                rank2 = market_reasons[0]
            else:
                rank1 = market_reasons[0]
                rank2 = market_reasons[1]
        else:
            company = "Other"
            # Cycle through the 5 dominant reasons for 240 respondents
            # Then give 12 respondents the rare reason (#7) — ~4.4% rate
            j = i - 30
            if j < 240:
                # Cycle through top 5 → each gets 48 mentions (~17.8%)
                idx = j % 5
                rank1 = market_reasons[idx]
                rank2 = market_reasons[(idx + 1) % 5]
            elif j < 252:
                # 12 respondents with "I didn't have time" → ~4.4% of non-FC
                rank1 = fc_top_reason
                rank2 = market_reasons[0]
            else:
                # Rest cycle through reasons 5-6
                idx = (j - 252) % 2 + 5
                rank1 = market_reasons[idx]
                rank2 = market_reasons[0]

        rows.append({
            "UniqueID": str(uid_val),
            "RenewalYearMonth": 202401,
            "Product": "Motor",
            "CurrentCompany": company,
            "IsSwitcher": False,
            "IsShopper": False,
            "Q19_rank1": rank1,
            "Q19_rank2": rank2,
            "Q19_rank3": None,
        })
        uid += 1

    return pd.DataFrame(rows)


@pytest.fixture
def ranked_df():
    return _make_ranked_df(n_respondents=300)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCalcReasonComparisonMarketLookup:
    """
    lib/analytics/reasons.py :: calc_reason_comparison

    Ensures market percentages are non-zero for reasons that appear in the
    insurer's top-N but rank outside the market's own top-5.
    """

    def test_insurer_reason_has_nonzero_market_pct_when_rare(self, ranked_df):
        """
        'I didn't have time' is rare market-wide but dominant for First Central.
        After indexing (via calc_reason_index), the market_pct must NOT be 0.

        This is the core regression test for spec 6c.
        The fix: market lookup uses a larger top_n so rare reasons are captured.
        """
        from lib.analytics.reasons import calc_reason_comparison, calc_reason_index

        result = calc_reason_comparison(ranked_df, "Q19", "First Central", top_n=5)

        assert result is not None
        ins_reasons = result["insurer"]
        mkt_reasons = result["market"]
        assert ins_reasons, "Insurer reasons should not be empty"

        # Run through the indexing step (as the screen does)
        indexed = calc_reason_index(ins_reasons, mkt_reasons)

        # Find "I didn't have time" in indexed list
        rare_indexed = next(
            (r for r in indexed if r["reason"] == "I didn't have time"),
            None,
        )
        assert rare_indexed is not None, (
            "'I didn't have time' should appear in First Central's indexed reasons"
        )

        # Market pct must NOT be zero — the reason exists market-wide (~5%)
        assert rare_indexed["market_pct"] > 0, (
            f"market_pct should be >0 for 'I didn't have time' but got "
            f"{rare_indexed['market_pct']!r}. "
            "This indicates the market top_n in calc_reason_comparison was too small "
            "to capture the rare reason in the market lookup."
        )

    def test_dominant_insurer_reasons_also_get_correct_market_pct(self, ranked_df):
        """
        Common reasons that appear in both insurer and market top-5 must still
        have correct market percentages (regression: fix must not break common cases).
        """
        from lib.analytics.reasons import calc_reason_comparison, calc_reason_index

        result = calc_reason_comparison(ranked_df, "Q19", "First Central", top_n=5)
        indexed = calc_reason_index(result["insurer"], result["market"])

        # "Price was too high" is common both at insurer and market level
        common = next(
            (r for r in indexed if r["reason"] == "Price was too high"),
            None,
        )
        if common is not None:
            assert common["market_pct"] > 0, (
                "'Price was too high' should have a positive market_pct"
            )

    def test_returns_both_insurer_and_market_keys(self, ranked_df):
        """Result dict always has 'insurer' and 'market' keys."""
        from lib.analytics.reasons import calc_reason_comparison

        result = calc_reason_comparison(ranked_df, "Q19", "First Central", top_n=5)
        assert "insurer" in result
        assert "market" in result

    def test_none_df_returns_none(self):
        """None DataFrame → returns None."""
        from lib.analytics.reasons import calc_reason_comparison

        result = calc_reason_comparison(None, "Q19", "First Central", top_n=5)
        assert result is None

    def test_empty_df_returns_none(self):
        """Empty DataFrame → returns None."""
        from lib.analytics.reasons import calc_reason_comparison

        result = calc_reason_comparison(pd.DataFrame(), "Q19", "First Central", top_n=5)
        assert result is None

    def test_missing_question_returns_none(self, ranked_df):
        """Question with no columns returns None."""
        from lib.analytics.reasons import calc_reason_comparison

        result = calc_reason_comparison(ranked_df, "Q99", "First Central", top_n=5)
        assert result is None

    def test_market_list_not_limited_to_insurer_top_n(self, ranked_df):
        """
        The market key may contain up to 20 reasons (large top_n), not just 5.
        This ensures the market lookup table is broad enough to find rare reasons.
        """
        from lib.analytics.reasons import calc_reason_comparison

        result = calc_reason_comparison(ranked_df, "Q19", "First Central", top_n=5)
        mkt_reasons = result.get("market", [])
        # With 10 distinct reasons in the data and market top_n=20, expect >5
        assert len(mkt_reasons) > 5, (
            f"Market reasons should include more than 5 entries when the data has 10 "
            f"distinct reasons, but got {len(mkt_reasons)}. "
            "Increase market top_n in calc_reason_comparison."
        )


class TestCalcReasonIndex:
    """
    lib/analytics/reasons.py :: calc_reason_index (dict-based, not scalar)

    Tests the aggregate version that takes list[dict] inputs.
    """

    def test_reason_in_market_list_gets_correct_index(self):
        """Standard case: reason present in both lists → index = brand/mkt * 100."""
        from lib.analytics.reasons import calc_reason_index

        ins = [{"reason": "Price", "rank1_pct": 0.50, "mention_pct": 0.50}]
        mkt = [{"reason": "Price", "rank1_pct": 0.25, "mention_pct": 0.25}]
        result = calc_reason_index(ins, mkt)
        assert len(result) == 1
        assert result[0]["reason"] == "Price"
        assert result[0]["index"] == pytest.approx(200.0)
        assert result[0]["brand_pct"] == pytest.approx(0.50)
        assert result[0]["market_pct"] == pytest.approx(0.25)

    def test_reason_not_in_market_gets_none_index(self):
        """Reason absent from market list → market_pct=0 → index=None."""
        from lib.analytics.reasons import calc_reason_index

        ins = [{"reason": "Rare reason", "rank1_pct": 0.10, "mention_pct": 0.10}]
        mkt = [{"reason": "Common reason", "rank1_pct": 0.50, "mention_pct": 0.50}]
        result = calc_reason_index(ins, mkt)
        assert len(result) == 1
        # market_pct=0 because reason not in market list → index should be None
        assert result[0]["market_pct"] == 0
        assert result[0]["index"] is None

    def test_empty_insurer_returns_empty_list(self):
        """Empty insurer list → empty result."""
        from lib.analytics.reasons import calc_reason_index

        result = calc_reason_index([], [{"reason": "X", "rank1_pct": 0.1}])
        assert result == []

    def test_empty_market_returns_empty_list(self):
        """Empty market list → empty result."""
        from lib.analytics.reasons import calc_reason_index

        result = calc_reason_index([{"reason": "X", "rank1_pct": 0.1}], [])
        assert result == []

    def test_uses_rank1_pct_for_ranked_questions(self):
        """rank1_pct takes precedence over mention_pct when present."""
        from lib.analytics.reasons import calc_reason_index

        ins = [{"reason": "Price", "rank1_pct": 0.40, "mention_pct": 0.80}]
        mkt = [{"reason": "Price", "rank1_pct": 0.20, "mention_pct": 0.60}]
        result = calc_reason_index(ins, mkt)
        # Should use rank1_pct: 0.40/0.20 = 200
        assert result[0]["index"] == pytest.approx(200.0)

    def test_uses_mention_pct_fallback_for_multi_select(self):
        """When rank1_pct not present, falls back to mention_pct."""
        from lib.analytics.reasons import calc_reason_index

        ins = [{"reason": "Hold other products", "mention_pct": 0.30}]
        mkt = [{"reason": "Hold other products", "mention_pct": 0.15}]
        result = calc_reason_index(ins, mkt)
        assert result[0]["index"] == pytest.approx(200.0)

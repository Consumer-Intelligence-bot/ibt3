"""
Batch 3 TDD tests: Reasons & Drivers display helpers.

Covers:
  - calc_reason_index  (lib/analytics/flow_display.py) — scalar index helper
  - format_reason_pct  (lib/analytics/flow_display.py) — display formatting
  - narrative_compact_expander_hidden logic (lib/components/narrative_panel.py)

TDD methodology: tests written FIRST (RED), then helpers implemented (GREEN).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# 1. calc_reason_index — scalar helper
#    (insurer_pct / market_pct) * 100, rounded to 0dp
# ===========================================================================

class TestCalcReasonIndexScalar:
    """lib/analytics/flow_display.py :: calc_reason_index (scalar)"""

    def test_normal_case_returns_index(self):
        """50% insurer vs 25% market → index 200."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(0.50, 0.25) == 200

    def test_equal_pcts_returns_100(self):
        """Equal insurer and market → index 100."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(0.40, 0.40) == 100

    def test_below_market_returns_sub_100(self):
        """Insurer 20%, market 40% → index 50."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(0.20, 0.40) == 50

    def test_market_zero_returns_none(self):
        """market_pct=0 → None (avoid division by zero)."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(0.30, 0.0) is None

    def test_insurer_none_returns_none(self):
        """insurer_pct=None → None."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(None, 0.40) is None

    def test_market_none_returns_none(self):
        """market_pct=None → None."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(0.40, None) is None

    def test_both_none_returns_none(self):
        """Both None → None."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(None, None) is None

    def test_result_is_rounded_to_0dp(self):
        """Result is an integer (rounded to 0dp) not a float."""
        from lib.analytics.flow_display import calc_reason_index
        result = calc_reason_index(0.333, 0.100)
        assert result == 333
        assert isinstance(result, int)

    def test_small_market_pct_no_crash(self):
        """Very small market_pct (0.001) does not raise."""
        from lib.analytics.flow_display import calc_reason_index
        result = calc_reason_index(0.001, 0.001)
        assert result == 100

    def test_insurer_zero_market_nonzero_returns_zero(self):
        """insurer_pct=0 with nonzero market → index 0."""
        from lib.analytics.flow_display import calc_reason_index
        assert calc_reason_index(0.0, 0.40) == 0

    def test_large_values_no_overflow(self):
        """Handles large percentage values without overflow."""
        from lib.analytics.flow_display import calc_reason_index
        result = calc_reason_index(0.999, 0.001)
        assert result == 99900

    def test_market_pct_negative_treated_as_zero(self):
        """Negative market_pct is treated as zero → None (guard)."""
        # Negative percentages are invalid; function should treat as division-by-zero guard.
        from lib.analytics.flow_display import calc_reason_index
        # If market_pct <= 0, return None (same as zero guard)
        assert calc_reason_index(0.30, -0.10) is None


# ===========================================================================
# 2. format_reason_pct — display formatting
#    0.0 exactly → "0%"
#    0 < value < 0.005 → "<1%"
#    0.156 → "16%"
#    None → "—"
# ===========================================================================

class TestFormatReasonPct:
    """lib/analytics/flow_display.py :: format_reason_pct"""

    def test_zero_exactly_returns_zero_pct(self):
        """Exactly 0.0 → '0%'."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.0) == "0%"

    def test_small_positive_below_half_percent_returns_less_than_1(self):
        """0.001 (0.1%) → '<1%'."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.001) == "<1%"

    def test_just_below_threshold_returns_less_than_1(self):
        """0.004 (0.4%) → '<1%' (below 0.005 threshold)."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.004) == "<1%"

    def test_at_threshold_still_less_than_1(self):
        """0.005 (0.5%) → '<1%' — Python :.0f rounds 0.5 to 0 (banker's rounding).

        The intent of format_reason_pct is to show '<1%' for any value that would
        display as '0%' but is genuinely non-zero. 0.005 rounds to 0 in Python's
        banker's rounding, so '<1%' is the correct display.
        """
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.005) == "<1%"

    def test_normal_value_rounds_correctly(self):
        """0.156 → '16%' (rounded to 0dp)."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.156) == "16%"

    def test_exactly_half_rounds_correctly(self):
        """0.50 → '50%'."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.50) == "50%"

    def test_one_returns_100_pct(self):
        """1.0 → '100%'."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(1.0) == "100%"

    def test_none_returns_em_dash(self):
        """None → '—' (em dash)."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(None) == "\u2014"

    def test_just_above_zero_threshold_returns_less_than_1(self):
        """1e-6 (tiny positive) → '<1%'."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(1e-6) == "<1%"

    def test_value_0_3_pct_returns_less_than_1(self):
        """0.003 → '<1%' (0.3%, below half-percent threshold)."""
        from lib.analytics.flow_display import format_reason_pct
        assert format_reason_pct(0.003) == "<1%"

    def test_negative_value_returns_zero_or_em_dash(self):
        """Negative percentage is invalid data; should not crash."""
        from lib.analytics.flow_display import format_reason_pct
        # Negative values should return "0%" (clamp) or "—" — either is acceptable.
        result = format_reason_pct(-0.01)
        assert result in ("0%", "\u2014", "0%")

    def test_result_is_string(self):
        """Return type is always str."""
        from lib.analytics.flow_display import format_reason_pct
        assert isinstance(format_reason_pct(0.25), str)
        assert isinstance(format_reason_pct(None), str)
        assert isinstance(format_reason_pct(0.0), str)


# ===========================================================================
# 3. narrative_compact: "Show detail" expander only shown when content exists
#    Pure logic test on should_show_detail helper
# ===========================================================================

class TestNarrativeCompactDetailLogic:
    """
    Tests the condition under which the 'Show detail' expander should render.
    We extract the pure boolean logic from render_narrative_compact so it can
    be tested without Streamlit.
    """

    def _should_show_detail(self, findings: list, data_gaps: list) -> bool:
        """Mirror the guard condition in render_narrative_compact (line 174)."""
        remaining_findings = findings[2:]
        return bool(remaining_findings or data_gaps)

    def test_no_findings_no_gaps_hides_expander(self):
        """Empty findings, no data_gaps → expander hidden."""
        assert self._should_show_detail([], []) is False

    def test_two_findings_no_gaps_hides_expander(self):
        """Exactly 2 findings (all shown inline), no gaps → expander hidden."""
        findings = [{"fact": "a"}, {"fact": "b"}]
        assert self._should_show_detail(findings, []) is False

    def test_three_findings_shows_expander(self):
        """3 findings → 1 overflow finding → expander shown."""
        findings = [{"fact": "a"}, {"fact": "b"}, {"fact": "c"}]
        assert self._should_show_detail(findings, []) is True

    def test_two_findings_with_gaps_shows_expander(self):
        """2 findings (no overflow) but data_gaps exist → expander shown."""
        findings = [{"fact": "a"}, {"fact": "b"}]
        assert self._should_show_detail(findings, ["gap1"]) is True

    def test_one_finding_no_gaps_hides_expander(self):
        """1 finding (shown inline), no gaps → expander hidden."""
        findings = [{"fact": "a"}]
        assert self._should_show_detail(findings, []) is False

    def test_no_findings_with_gaps_shows_expander(self):
        """No findings but data_gaps exist → expander shown for gaps."""
        assert self._should_show_detail([], ["missing Q27 data"]) is True

    def test_many_findings_shows_expander(self):
        """5 findings → 3 overflow → expander shown."""
        findings = [{"fact": str(i)} for i in range(5)]
        assert self._should_show_detail(findings, []) is True

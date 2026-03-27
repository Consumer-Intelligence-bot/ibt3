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

    The updated rule (Spec 6e fix):
    - Show expander if any inline finding has an 'Investigate' prompt, OR
      there are remaining (overflow) findings, OR there are data_gaps.
    - Hide expander if there are no findings, no data_gaps, and no investigate
      prompts in the inline findings.
    """

    def _should_show_detail(self, findings: list, data_gaps: list) -> bool:
        """Updated guard: show when inline findings have prompts, overflow
        exists, or data_gaps exist. Mirrors _should_show_detail() in
        narrative_panel.py."""
        from lib.components.narrative_panel import _should_show_detail
        return _should_show_detail(findings, data_gaps)

    def test_no_findings_no_gaps_hides_expander(self):
        """Empty findings, no data_gaps → expander hidden."""
        assert self._should_show_detail([], []) is False

    def test_two_findings_no_gaps_hides_expander(self):
        """2 findings with NO prompts, no gaps → expander hidden (nothing more to show)."""
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
        """1 finding with no prompt, no gaps → expander hidden."""
        findings = [{"fact": "a"}]
        assert self._should_show_detail(findings, []) is False

    def test_no_findings_with_gaps_shows_expander(self):
        """No findings but data_gaps exist → expander shown for gaps."""
        assert self._should_show_detail([], ["missing Q27 data"]) is True

    def test_many_findings_shows_expander(self):
        """5 findings → 3 overflow → expander shown."""
        findings = [{"fact": str(i)} for i in range(5)]
        assert self._should_show_detail(findings, []) is True

    def test_one_finding_with_prompt_shows_expander(self):
        """1 inline finding WITH an investigate prompt → expander shown so
        the prompt is accessible (key fix for Spec 6e)."""
        findings = [{"fact": "a", "observation": "b", "prompt": "Why?"}]
        assert self._should_show_detail(findings, []) is True

    def test_two_findings_with_prompts_shows_expander(self):
        """2 inline findings both with investigate prompts → expander shown."""
        findings = [
            {"fact": "a", "observation": "b", "prompt": "Why a?"},
            {"fact": "c", "observation": "d", "prompt": "Why c?"},
        ]
        assert self._should_show_detail(findings, []) is True

    def test_finding_with_empty_prompt_hides_expander(self):
        """Inline finding with empty string prompt → treated as no prompt → expander hidden."""
        findings = [{"fact": "a", "observation": "b", "prompt": ""}]
        assert self._should_show_detail(findings, []) is False

    def test_finding_with_none_prompt_hides_expander(self):
        """Inline finding with None prompt → treated as no prompt → expander hidden."""
        findings = [{"fact": "a", "observation": "b", "prompt": None}]
        assert self._should_show_detail(findings, []) is False


# ===========================================================================
# 4. narrative_compact: detail expander content (Spec 6e)
#    Pure logic tests on _detail_content helper
# ===========================================================================

class TestNarrativeCompactDetailContent:
    """
    Tests the content that appears inside the 'Show detail' expander.

    The updated rule (Spec 6e fix):
    - Always show investigate prompts for the inline findings (findings[:2])
      if they have prompts, so clicking 'Show detail' reveals MORE than the
      compact view, not less.
    - Then show remaining findings in full (Fact / Observation / Investigate).
    - Then show data_gaps if any.
    """

    def _detail_content(self, findings: list, data_gaps: list) -> dict:
        """Call the helper from narrative_panel that computes what goes in the
        detail expander. Returns a dict with:
          'inline_prompts': list of (fact, prompt) for the inline findings
          'overflow_findings': list of finding dicts for findings[2:]
          'data_gaps': the data_gaps list
        """
        from lib.components.narrative_panel import _detail_content
        return _detail_content(findings, data_gaps)

    def test_one_finding_with_prompt_returns_inline_prompt(self):
        """1 finding with prompt → inline_prompts has 1 entry."""
        findings = [{"fact": "Retention is 72%", "observation": "Above avg", "prompt": "What drives this?"}]
        result = self._detail_content(findings, [])
        assert len(result["inline_prompts"]) == 1
        assert result["inline_prompts"][0]["fact"] == "Retention is 72%"
        assert result["inline_prompts"][0]["prompt"] == "What drives this?"

    def test_two_findings_with_prompts_returns_both_inline_prompts(self):
        """2 findings with prompts → inline_prompts has 2 entries."""
        findings = [
            {"fact": "a", "prompt": "Why a?"},
            {"fact": "b", "prompt": "Why b?"},
        ]
        result = self._detail_content(findings, [])
        assert len(result["inline_prompts"]) == 2

    def test_three_findings_inline_prompts_only_for_first_two(self):
        """3 findings → inline_prompts covers only first 2, overflow covers finding 3."""
        findings = [
            {"fact": "a", "prompt": "Why a?"},
            {"fact": "b", "prompt": "Why b?"},
            {"fact": "c", "prompt": "Why c?"},
        ]
        result = self._detail_content(findings, [])
        assert len(result["inline_prompts"]) == 2
        assert len(result["overflow_findings"]) == 1
        assert result["overflow_findings"][0]["fact"] == "c"

    def test_finding_without_prompt_excluded_from_inline_prompts(self):
        """Finding with no prompt is excluded from inline_prompts list."""
        findings = [{"fact": "a"}]
        result = self._detail_content(findings, [])
        assert result["inline_prompts"] == []

    def test_data_gaps_passed_through(self):
        """data_gaps are returned unchanged in the content dict."""
        result = self._detail_content([], ["gap1", "gap2"])
        assert result["data_gaps"] == ["gap1", "gap2"]

    def test_empty_everything_returns_empty_content(self):
        """No findings, no gaps → all lists empty."""
        result = self._detail_content([], [])
        assert result["inline_prompts"] == []
        assert result["overflow_findings"] == []
        assert result["data_gaps"] == []

    def test_overflow_findings_included_in_full(self):
        """Overflow findings include all three fields: fact, observation, prompt."""
        findings = [
            {"fact": "a"}, {"fact": "b"},
            {"fact": "c", "observation": "obs_c", "prompt": "prompt_c"},
        ]
        result = self._detail_content(findings, [])
        overflow = result["overflow_findings"]
        assert len(overflow) == 1
        assert overflow[0]["fact"] == "c"
        assert overflow[0]["observation"] == "obs_c"
        assert overflow[0]["prompt"] == "prompt_c"

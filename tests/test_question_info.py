"""
Tests for question info components.

TDD: tests written before implementation.

Covers:
  - QUESTION_MAP structure and completeness (lib/data/question_map.py)
  - render_question_info behaviour (lib/components/question_info.py)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# TestQuestionMap
# ===========================================================================

class TestQuestionMap:
    """lib/data/question_map.py :: QUESTION_MAP"""

    def test_question_map_is_dict(self):
        """QUESTION_MAP must be a plain dict."""
        from lib.data.question_map import QUESTION_MAP
        assert isinstance(QUESTION_MAP, dict)

    def test_all_expected_keys_present(self):
        """All question IDs referenced in the brief must exist in QUESTION_MAP."""
        from lib.data.question_map import QUESTION_MAP
        expected = [
            "Q1", "Q2", "Q3", "Q6", "Q6a", "Q6b",
            "Q7", "Q8", "Q9a", "Q18", "Q19",
            "Q21", "Q27", "Q31", "Q33",
            "Q47", "Q48", "Q52",
        ]
        missing = [q for q in expected if q not in QUESTION_MAP]
        assert missing == [], f"Missing keys in QUESTION_MAP: {missing}"

    def test_each_entry_has_text_key(self):
        """Every entry must have a 'text' key."""
        from lib.data.question_map import QUESTION_MAP
        missing_text = [k for k, v in QUESTION_MAP.items() if "text" not in v]
        assert missing_text == [], f"Entries missing 'text': {missing_text}"

    def test_each_entry_has_calc_key(self):
        """Every entry must have a 'calc' key."""
        from lib.data.question_map import QUESTION_MAP
        missing_calc = [k for k, v in QUESTION_MAP.items() if "calc" not in v]
        assert missing_calc == [], f"Entries missing 'calc': {missing_calc}"

    def test_no_empty_text_values(self):
        """No entry should have an empty 'text' string."""
        from lib.data.question_map import QUESTION_MAP
        empty_text = [k for k, v in QUESTION_MAP.items() if not v.get("text", "").strip()]
        assert empty_text == [], f"Entries with empty 'text': {empty_text}"

    def test_no_empty_calc_values(self):
        """No entry should have an empty 'calc' string."""
        from lib.data.question_map import QUESTION_MAP
        empty_calc = [k for k, v in QUESTION_MAP.items() if not v.get("calc", "").strip()]
        assert empty_calc == [], f"Entries with empty 'calc': {empty_calc}"

    def test_spot_check_q6_text(self):
        """Q6 text must reference the premium comparison concept."""
        from lib.data.question_map import QUESTION_MAP
        assert "renewal" in QUESTION_MAP["Q6"]["text"].lower() or "premium" in QUESTION_MAP["Q6"]["text"].lower()

    def test_spot_check_q47_text(self):
        """Q47 text must reference satisfaction."""
        from lib.data.question_map import QUESTION_MAP
        assert "satisfied" in QUESTION_MAP["Q47"]["text"].lower() or "satisfaction" in QUESTION_MAP["Q47"]["text"].lower()

    def test_spot_check_q48_nps(self):
        """Q48 calc must reference NPS."""
        from lib.data.question_map import QUESTION_MAP
        assert "nps" in QUESTION_MAP["Q48"]["calc"].lower() or "recommend" in QUESTION_MAP["Q48"]["calc"].lower()


# ===========================================================================
# TestRenderQuestionInfo
# ===========================================================================

class TestRenderQuestionInfo:
    """lib/components/question_info.py :: render_question_info"""

    def _mock_streamlit(self, monkeypatch):
        """
        Patch streamlit so render_question_info can be called outside a
        Streamlit app context. Records calls to st.expander and st.markdown.
        """
        calls = {"expander": [], "markdown": []}

        class _MockExpander:
            def __init__(self, label, expanded=False):
                calls["expander"].append({"label": label, "expanded": expanded})

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def _mock_markdown(text, **kwargs):
            calls["markdown"].append(text)

        import streamlit as st
        monkeypatch.setattr(st, "expander", _MockExpander)
        monkeypatch.setattr(st, "markdown", _mock_markdown)
        return calls

    def test_accepts_single_string(self, monkeypatch):
        """render_question_info must accept a bare string question ID."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        # Should not raise
        render_question_info("Q6")
        assert len(calls["expander"]) == 1

    def test_accepts_list_of_strings(self, monkeypatch):
        """render_question_info must accept a list of question IDs."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info(["Q6", "Q6a", "Q6b"])
        assert len(calls["expander"]) == 1

    def test_unknown_question_id_renders_nothing(self, monkeypatch):
        """An unknown question ID must not raise and must not open an expander."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info("Q_DOES_NOT_EXIST")
        assert len(calls["expander"]) == 0

    def test_empty_list_renders_nothing(self, monkeypatch):
        """An empty list must not open an expander."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info([])
        assert len(calls["expander"]) == 0

    def test_mixed_known_and_unknown_renders_expander(self, monkeypatch):
        """A list with one known and one unknown ID should still render the expander."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info(["Q6", "Q_UNKNOWN"])
        assert len(calls["expander"]) == 1

    def test_expander_label_contains_info(self, monkeypatch):
        """The expander label must include 'About this data' (case-insensitive)."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info("Q6")
        label = calls["expander"][0]["label"]
        assert "about this data" in label.lower()

    def test_expander_collapsed_by_default(self, monkeypatch):
        """The expander must be collapsed by default (expanded=False)."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info("Q6")
        assert calls["expander"][0]["expanded"] is False

    def test_markdown_contains_question_id(self, monkeypatch):
        """The markdown content must reference the question ID."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info("Q6")
        combined = " ".join(calls["markdown"])
        assert "Q6" in combined

    def test_multiple_questions_all_appear_in_markdown(self, monkeypatch):
        """All known question IDs passed should appear in the rendered markdown."""
        calls = self._mock_streamlit(monkeypatch)
        from lib.components.question_info import render_question_info
        render_question_info(["Q47", "Q48"])
        combined = " ".join(calls["markdown"])
        assert "Q47" in combined
        assert "Q48" in combined

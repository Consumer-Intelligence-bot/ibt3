"""
Question info expander component.

Renders a collapsible "About this data" panel showing the verbatim survey
question text and calculation method for one or more question IDs.
"""

from __future__ import annotations

import streamlit as st

from lib.data.question_map import QUESTION_MAP


def render_question_info(question_ids: str | list[str]) -> None:
    """Render an expandable info section showing the survey question text.

    Parameters
    ----------
    question_ids:
        One or more question IDs (e.g. ``"Q6"`` or ``["Q6", "Q6a", "Q6b"]``).
        Unknown IDs are silently skipped. If no known IDs are provided,
        nothing is rendered.
    """
    if isinstance(question_ids, str):
        question_ids = [question_ids]

    entries: list[str] = []
    for qid in question_ids:
        q = QUESTION_MAP.get(qid)
        if q:
            entries.append(f"**{qid}:** {q['text']}\n\n*Calculation:* {q['calc']}")

    if not entries:
        return

    with st.expander("ℹ About this data", expanded=False):
        st.markdown("\n\n---\n\n".join(entries))

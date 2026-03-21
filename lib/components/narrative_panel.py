"""
Collapsible AI narrative panel.

Default expanded. Collapse state persists via st.session_state["narrative_collapsed"].
"""

import streamlit as st

from lib.config import CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, CI_VIOLET
from lib.formatting import FONT


def render_narrative_panel(narrative: dict | None, screen_name: str = ""):
    """Render a collapsible narrative panel.

    Parameters
    ----------
    narrative : dict | None
        Dict with 'headline' and optionally 'findings' list of
        {fact, observation, prompt} dicts. If None, shows unavailable message.
    screen_name : str
        Used for unique widget key.
    """
    if narrative is None:
        st.caption("AI narrative unavailable. Ensure ANTHROPIC_API_KEY is set.")
        return

    # Use expander for collapsible behaviour
    with st.expander("AI Narrative", expanded=not st.session_state.get("narrative_collapsed", False)):
        headline = narrative.get("headline", "")
        if headline:
            st.markdown(
                f'<div style="font-size:16px; font-weight:bold; color:{CI_VIOLET}; '
                f'margin-bottom:8px; font-family:{FONT};">{headline}</div>',
                unsafe_allow_html=True,
            )

        subtitle = narrative.get("subtitle", "")
        if subtitle:
            st.markdown(
                f'<div style="font-size:13px; color:{CI_GREY}; font-style:italic; '
                f'margin-bottom:12px; font-family:{FONT};">{subtitle}</div>',
                unsafe_allow_html=True,
            )

        paragraph = narrative.get("paragraph", "")
        if paragraph:
            st.markdown(
                f'<div style="font-size:13px; color:{CI_GREY}; line-height:1.6; '
                f'font-family:{FONT};">{paragraph}</div>',
                unsafe_allow_html=True,
            )

        findings = narrative.get("findings", [])
        for finding in findings:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; color:{CI_GREY}; '
                f'margin-bottom:12px; padding:10px 14px; background:{CI_LIGHT_GREY}; '
                f'border-radius:4px;">'
                f'<div style="margin-bottom:4px;"><b>Fact:</b> {finding.get("fact", "")}</div>'
                f'<div style="margin-bottom:4px;"><b>Observation:</b> {finding.get("observation", "")}</div>'
                f'<div><b>Investigate:</b> {finding.get("prompt", "")}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        data_gaps = narrative.get("data_gaps", [])
        if data_gaps:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; color:{CI_GREY}; '
                f'margin-top:12px; padding:8px 14px; border-left:3px solid #FFCD00;">'
                f'<b>Data gaps:</b> {" | ".join(data_gaps)}</div>',
                unsafe_allow_html=True,
            )

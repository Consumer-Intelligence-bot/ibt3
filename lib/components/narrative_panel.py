"""
Collapsible AI narrative panel.

Default expanded. Uses Streamlit expander with editorial styling.
"""

import streamlit as st

from lib.config import CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, CI_NAVY, CI_VIOLET
from lib.formatting import FONT, FONT_DISPLAY


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

    with st.expander("AI Narrative", expanded=not st.session_state.get("narrative_collapsed", False)):
        headline = narrative.get("headline", "")
        if headline:
            st.markdown(
                f'<div style="font-family:{FONT_DISPLAY}; font-size:18px; font-weight:600; '
                f'color:{CI_NAVY}; margin-bottom:8px; line-height:1.3;">{headline}</div>',
                unsafe_allow_html=True,
            )

        subtitle = narrative.get("subtitle", "")
        if subtitle:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; color:#8B94A8; '
                f'font-style:italic; margin-bottom:14px;">{subtitle}</div>',
                unsafe_allow_html=True,
            )

        paragraph = narrative.get("paragraph", "")
        if paragraph:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; color:{CI_GREY}; '
                f'line-height:1.7;">{paragraph}</div>',
                unsafe_allow_html=True,
            )

        findings = narrative.get("findings", [])
        for finding in findings:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; color:{CI_GREY}; '
                f'margin:12px 0; padding:14px 18px; background:white; '
                f'border-left:3px solid {CI_MAGENTA}; border-radius:0 4px 4px 0;">'
                f'<div style="margin-bottom:6px;"><span style="font-weight:700; '
                f'color:{CI_NAVY}; font-size:10px; text-transform:uppercase; '
                f'letter-spacing:0.8px;">Fact</span><br>{finding.get("fact", "")}</div>'
                f'<div style="margin-bottom:6px;"><span style="font-weight:700; '
                f'color:{CI_NAVY}; font-size:10px; text-transform:uppercase; '
                f'letter-spacing:0.8px;">Observation</span><br>{finding.get("observation", "")}</div>'
                f'<div><span style="font-weight:700; color:{CI_MAGENTA}; font-size:10px; '
                f'text-transform:uppercase; letter-spacing:0.8px;">Investigate</span>'
                f'<br>{finding.get("prompt", "")}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        data_gaps = narrative.get("data_gaps", [])
        if data_gaps:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:11px; color:#8B94A8; '
                f'margin-top:14px; padding:10px 16px; border-left:3px solid #FFCD00; '
                f'background:rgba(255,205,0,0.06); border-radius:0 4px 4px 0;">'
                f'<span style="font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">'
                f'Data gaps</span><br>{" | ".join(data_gaps)}</div>',
                unsafe_allow_html=True,
            )

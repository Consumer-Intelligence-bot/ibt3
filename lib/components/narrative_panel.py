"""
AI narrative panels.

Two variants:
- render_narrative_panel(): Full collapsible expander (legacy, full-width).
- render_narrative_compact(): Compact top-of-screen variant for Decision Screen
  layout. Always visible, headline + paragraph + top 2 findings, with
  "Show detail" expander for the rest.
"""

import streamlit as st

from lib.config import (
    CI_CHARCOAL, CI_CHARCOAL_60, CI_CHARCOAL_20, CI_PURPLE, CI_YELLOW, FONT,
)
from lib.formatting import FONT as _FONT


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
                f'<div style="font-family:{FONT}; font-size:20px; font-weight:700; '
                f'color:{CI_CHARCOAL}; margin-bottom:8px; line-height:1.3;">{headline}</div>',
                unsafe_allow_html=True,
            )

        subtitle = narrative.get("subtitle", "")
        if subtitle:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:15px; color:{CI_CHARCOAL_60}; '
                f'font-style:italic; margin-bottom:14px;">{subtitle}</div>',
                unsafe_allow_html=True,
            )

        paragraph = narrative.get("paragraph", "")
        if paragraph:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:15px; color:{CI_CHARCOAL}; '
                f'line-height:1.7;">{paragraph}</div>',
                unsafe_allow_html=True,
            )

        findings = narrative.get("findings", [])
        for finding in findings:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:14px; color:{CI_CHARCOAL}; '
                f'margin:12px 0; padding:14px 18px; background:white; '
                f'border-left:3px solid {CI_PURPLE}; border-radius:0 12px 12px 0;">'
                f'<div style="margin-bottom:6px;"><span style="font-weight:700; '
                f'color:{CI_CHARCOAL}; font-size:10px; text-transform:uppercase; '
                f'letter-spacing:0.8px;">Fact</span><br>{finding.get("fact", "")}</div>'
                f'<div style="margin-bottom:6px;"><span style="font-weight:700; '
                f'color:{CI_CHARCOAL}; font-size:10px; text-transform:uppercase; '
                f'letter-spacing:0.8px;">Observation</span><br>{finding.get("observation", "")}</div>'
                f'<div><span style="font-weight:700; color:{CI_PURPLE}; font-size:10px; '
                f'text-transform:uppercase; letter-spacing:0.8px;">Investigate</span>'
                f'<br>{finding.get("prompt", "")}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        data_gaps = narrative.get("data_gaps", [])
        if data_gaps:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:11px; color:{CI_CHARCOAL_60}; '
                f'margin-top:14px; padding:10px 16px; border-left:3px solid {CI_YELLOW}; '
                f'background:rgba(255,205,0,0.06); border-radius:0 12px 12px 0;">'
                f'<span style="font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">'
                f'Data gaps</span><br>{" | ".join(data_gaps)}</div>',
                unsafe_allow_html=True,
            )


def render_narrative_compact(narrative: dict | None, screen_name: str = ""):
    """Render a compact AI narrative at the top of a Decision Screen.

    Always visible (no expander wrapper). Shows headline, paragraph, and up
    to 2 findings inline. Additional findings and data gaps are tucked into
    a "Show detail" expander.

    Parameters
    ----------
    narrative : dict | None
        Same shape as render_narrative_panel. If None, renders nothing.
    screen_name : str
        Used for unique widget keys.
    """
    if narrative is None:
        return

    headline = narrative.get("headline", "")
    paragraph = narrative.get("paragraph", "")
    subtitle = narrative.get("subtitle", "")
    findings = narrative.get("findings", [])
    data_gaps = narrative.get("data_gaps", [])

    if not headline and not paragraph:
        return

    # Outer container
    st.markdown(
        f'<div style="'
        f'background:white; border:1px solid {CI_CHARCOAL_20}; '
        f'border-left:4px solid {CI_PURPLE}; border-radius:12px; '
        f'padding:14px 18px; margin-bottom:12px; font-family:{FONT};">',
        unsafe_allow_html=True,
    )

    # Label
    st.markdown(
        f'<div style="font-size:9px; font-weight:700; text-transform:uppercase; '
        f'letter-spacing:1px; color:{CI_CHARCOAL_60}; margin-bottom:6px;">'
        f'AI Narrative</div>',
        unsafe_allow_html=True,
    )

    # Headline
    if headline:
        st.markdown(
            f'<div style="font-size:17px; font-weight:700; color:{CI_CHARCOAL}; '
            f'line-height:1.3; margin-bottom:6px;">{headline}</div>',
            unsafe_allow_html=True,
        )

    # Subtitle
    if subtitle:
        st.markdown(
            f'<div style="font-size:14px; color:{CI_CHARCOAL_60}; '
            f'font-style:italic; margin-bottom:8px;">{subtitle}</div>',
            unsafe_allow_html=True,
        )

    # Paragraph
    if paragraph:
        st.markdown(
            f'<div style="font-size:14px; color:{CI_CHARCOAL}; '
            f'line-height:1.6; margin-bottom:8px;">{paragraph}</div>',
            unsafe_allow_html=True,
        )

    # Top 2 findings inline
    for finding in findings[:2]:
        fact = finding.get("fact", "")
        observation = finding.get("observation", "")
        st.markdown(
            f'<div style="font-size:13px; color:{CI_CHARCOAL}; '
            f'padding:6px 10px; margin:4px 0; background:{CI_CHARCOAL_20}; '
            f'border-radius:8px;">'
            f'<span style="font-weight:700; color:{CI_PURPLE}; font-size:10px; '
            f'text-transform:uppercase; letter-spacing:0.5px;">Fact</span> '
            f'{fact}'
            f'{"  —  " + observation if observation else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Close outer container
    st.markdown('</div>', unsafe_allow_html=True)

    # Overflow: remaining findings + data gaps
    remaining_findings = findings[2:]
    if remaining_findings or data_gaps:
        with st.expander("Show detail", expanded=False):
            for finding in remaining_findings:
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; color:{CI_CHARCOAL}; '
                    f'margin:8px 0; padding:10px 14px; background:white; '
                    f'border-left:3px solid {CI_PURPLE}; border-radius:0 12px 12px 0;">'
                    f'<div style="margin-bottom:4px;"><span style="font-weight:700; '
                    f'color:{CI_CHARCOAL}; font-size:9px; text-transform:uppercase; '
                    f'letter-spacing:0.8px;">Fact</span><br>{finding.get("fact", "")}</div>'
                    f'<div style="margin-bottom:4px;"><span style="font-weight:700; '
                    f'color:{CI_CHARCOAL}; font-size:9px; text-transform:uppercase; '
                    f'letter-spacing:0.8px;">Observation</span><br>{finding.get("observation", "")}</div>'
                    f'<div><span style="font-weight:700; color:{CI_PURPLE}; font-size:9px; '
                    f'text-transform:uppercase; letter-spacing:0.8px;">Investigate</span>'
                    f'<br>{finding.get("prompt", "")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if data_gaps:
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:11px; color:{CI_CHARCOAL_60}; '
                    f'margin-top:8px; padding:8px 14px; border-left:3px solid {CI_YELLOW}; '
                    f'background:rgba(255,205,0,0.06); border-radius:0 12px 12px 0;">'
                    f'<span style="font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">'
                    f'Data gaps</span><br>{" | ".join(data_gaps)}</div>',
                    unsafe_allow_html=True,
                )

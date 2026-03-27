"""
Context footer for Decision Screen layout.

Shows data freshness, methodology link, sample size, and confidence level.
Mandatory trust indicators on every data view.
"""

import streamlit as st

from lib.config import CI_CHARCOAL, CI_CHARCOAL_20, CI_CHARCOAL_60, CI_CYAN, CI_GREEN, CI_YELLOW, CI_RED, FONT
from lib.components.methodology_dialog import render_methodology_button


def _confidence_label(n: int) -> tuple[str, str]:
    """Return (label, colour) for a sample size."""
    if n >= 100:
        return "High confidence", CI_CYAN  # was CI_GREEN — avoid clash with positive KPI accent
    if n >= 30:
        return "Indicative", CI_YELLOW
    return "Low confidence", CI_RED


def render_context_footer(
    *,
    screen_name: str = "",
    product: str = "",
    period: str = "",
    sample_n: int | None = None,
    last_refreshed: str | None = None,
    show_methodology_link: bool = True,
):
    """Render a context footer with trust indicators.

    Parameters
    ----------
    screen_name : str
        Current screen name for attribution.
    product : str
        Product name (Motor, Home, Pet).
    period : str
        Human-readable period label.
    sample_n : int | None
        Total sample size. None to hide confidence badge.
    last_refreshed : str | None
        Timestamp string. Falls back to session state if None.
    show_methodology_link : bool
        Whether to show the methodology navigation button.
    """
    # Resolve refresh time
    if last_refreshed is None:
        last_refreshed = st.session_state.get("last_refresh_time", "Unknown")

    # Build footer parts
    parts = []

    if product:
        parts.append(f"Source: IBT {product}")
    if period:
        parts.append(period)

    if sample_n is not None:
        conf_label, conf_colour = _confidence_label(sample_n)
        parts.append(
            f'n={sample_n:,} '
            f'<span style="display:inline-block; padding:1px 6px; border-radius:8px; '
            f'font-size:9px; font-weight:600; background:{conf_colour}20; '
            f'color:{conf_colour};">{conf_label}</span>'
        )

    parts.append(f"Last updated: {last_refreshed}")

    separator = f' <span style="color:{CI_CHARCOAL_60};">&middot;</span> '

    st.markdown(
        f'<div style="'
        f'border-top:1px solid {CI_CHARCOAL_20}; margin-top:24px; padding-top:10px; '
        f'font-family:{FONT}; font-size:11px; color:{CI_CHARCOAL_60}; '
        f'line-height:1.8;">'
        f'{separator.join(parts)}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if show_methodology_link:
        render_methodology_button(screen_name)

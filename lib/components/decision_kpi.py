"""
Decision Screen KPI card with trend arrow, change value, and confidence badge.

Renders a row of 3-5 KPI cards in the Decision Screen layout.
Each card shows: title, primary value, trend arrow with change,
and a confidence badge (sample size with colour coding).
"""

import streamlit as st

from lib.config import (
    CI_CHARCOAL, CI_CHARCOAL_20, CI_CHARCOAL_60,
    CI_CYAN, CI_GREEN, CI_PURPLE, CI_RED, CI_YELLOW,
    FONT,
)


def _trend_arrow(trend: str) -> tuple[str, str]:
    """Return (arrow character, colour) for a trend direction."""
    if trend == "up":
        return "\u25b2", CI_GREEN
    if trend == "down":
        return "\u25bc", CI_RED
    return "\u25b6", CI_CHARCOAL_60


def _confidence_colour(n: int) -> str:
    """Return badge colour based on sample size."""
    if n >= 100:
        return CI_GREEN
    if n >= 30:
        return CI_YELLOW
    return CI_RED


def decision_kpi(
    title: str,
    value: str,
    *,
    change: str = "",
    trend: str = "flat",
    sample_n: int | None = None,
    colour: str | None = None,
    caption: str = "",
):
    """Render a single Decision Screen KPI card.

    Parameters
    ----------
    title : str
        Uppercase label (e.g. "Retention Rate").
    value : str
        Primary metric display (e.g. "72.3%").
    change : str
        Change label (e.g. "+3.2pp", "-1.1%"). Empty string to hide.
    trend : str
        One of "up", "down", "flat". Drives arrow and colour.
    sample_n : int | None
        Sample size for confidence badge. None to hide badge.
    colour : str | None
        Accent colour for the card. Defaults to CI_PURPLE.
    caption : str
        Optional small text below the badge, e.g. a CI range or definition.
        Empty string to hide.
    """
    if colour is None:
        colour = CI_PURPLE

    arrow, arrow_colour = _trend_arrow(trend)

    # Change + arrow row
    change_html = ""
    if change:
        change_html = (
            f'<div style="font-size:13px; font-weight:600; color:{arrow_colour}; '
            f'margin-top:4px;">'
            f'{arrow} {change}</div>'
        )

    # Confidence badge
    badge_html = ""
    if sample_n is not None:
        badge_colour = _confidence_colour(sample_n)
        badge_html = (
            f'<div style="display:inline-block; margin-top:8px; padding:2px 8px; '
            f'border-radius:12px; font-size:10px; font-weight:600; '
            f'background:{badge_colour}20; color:{badge_colour}; '
            f'letter-spacing:0.3px;">n={sample_n:,}</div>'
        )

    # Optional caption (CI range, definition, etc.)
    caption_html = ""
    if caption:
        caption_html = (
            f'<div style="font-size:10px; color:{CI_CHARCOAL_60}; '
            f'margin-top:6px; font-style:italic;">{caption}</div>'
        )

    st.markdown(
        f'<div style="'
        f'background:white; border:1px solid {CI_CHARCOAL_20}; '
        f'border-left:4px solid {colour}; border-radius:12px; '
        f'padding:14px 18px; min-height:100px; font-family:{FONT}; '
        f'transition:box-shadow 0.2s ease;">'
        f'<div style="font-size:10px; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.8px; color:{CI_CHARCOAL_60}; margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:28px; font-weight:700; color:{colour}; '
        f'line-height:1.1;">{value}</div>'
        f'{change_html}'
        f'{badge_html}'
        f'{caption_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def decision_kpi_row(kpis: list[dict]):
    """Render a row of Decision Screen KPI cards.

    Parameters
    ----------
    kpis : list[dict]
        Each dict is passed as kwargs to ``decision_kpi()``.
        Required keys: title, value.
        Optional keys: change, trend, sample_n, colour.

    Example::

        decision_kpi_row([
            {"title": "Retention", "value": "72.3%", "change": "+3.2pp", "trend": "up", "sample_n": 1240},
            {"title": "Switching", "value": "18.1%", "change": "-1.1pp", "trend": "down", "sample_n": 1240},
            {"title": "Net Flow", "value": "+47", "trend": "up", "sample_n": 1240},
        ])
    """
    if not kpis:
        return

    cols = st.columns(len(kpis))
    for col, kpi_kwargs in zip(cols, kpis):
        with col:
            decision_kpi(**kpi_kwargs)

"""
Shared formatting utilities for Consumer Intelligence dashboard pages.
"""

import base64
from pathlib import Path

import streamlit as st

from lib.config import CI_GREY, CI_LIGHT_GREY, CSS

FONT = "Verdana, Geneva, sans-serif"

# Pre-compute logo base64 once at module load
_LOGO_PATH = Path(__file__).parent.parent / "assets" / "ci_logo.png"
_LOGO_B64 = ""
if _LOGO_PATH.exists():
    _LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()


def render_header():
    """Render the CI branded header with logo. Call at the top of every page."""
    st.markdown(CSS, unsafe_allow_html=True)
    logo_tag = f'<img src="data:image/png;base64,{_LOGO_B64}" alt="CI Logo">' if _LOGO_B64 else ""
    st.markdown(
        f'<div class="ci-header">'
        f'{logo_tag}'
        f'<span class="ci-logo">Consumer Intelligence</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def fmt_pct(val, dp=1):
    """Format a proportion (0-1) as a percentage string."""
    if val is None:
        return "\u2014"
    return f"{val * 100:.{dp}f}%"


def safe_pct(n, d):
    """Divide n by d, returning 0.0 if d is zero."""
    return n / d if d > 0 else 0.0


def section_divider(title):
    """Render a branded section divider."""
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:15px; font-weight:bold; color:{CI_GREY}; '
        f'border-bottom:2px solid {CI_LIGHT_GREY}; padding-bottom:8px; margin:28px 0 16px 0;">'
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def period_label(selected_months):
    """Build a human-readable period label from selected months."""
    from lib.state import format_year_month

    if not selected_months:
        return "All periods"
    start = format_year_month(min(selected_months))
    end = format_year_month(max(selected_months))
    if start == end:
        return start
    return f"{start} \u2013 {end}"


def card_html(title, value, subtitle="", colour=None):
    """Render a styled metric card as HTML."""
    from lib.config import CI_MAGENTA
    if colour is None:
        colour = CI_MAGENTA
    return (
        f'<div style="background:white; border:1px solid {CI_LIGHT_GREY}; border-top:4px solid {colour}; '
        f'border-radius:4px; padding:16px 20px; text-align:center; font-family:{FONT};">'
        f'<div style="font-size:12px; color:{CI_GREY}; margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:28px; font-weight:bold; color:{colour};">{value}</div>'
        f'<div style="font-size:11px; color:{CI_GREY}; margin-top:4px;">{subtitle}</div>'
        f"</div>"
    )

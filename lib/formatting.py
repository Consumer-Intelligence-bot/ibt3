"""
Shared formatting utilities for Consumer Intelligence dashboard pages.
"""

from pathlib import Path

import streamlit as st

from lib.config import CI_CHARCOAL_60, CI_GREY, CI_LIGHT_GREY, CSS, FONT as _FONT

FONT = _FONT
FONT_DISPLAY = FONT  # Montserrat 700 for display; no separate display font

# Pre-load logo bytes once at module load
_LOGO_PATH = Path(__file__).parent.parent / "assets" / "ci_logo.png"
_LOGO_BYTES = _LOGO_PATH.read_bytes() if _LOGO_PATH.exists() else None


def render_header():
    """Inject CSS and place CI logo in the sidebar. Call at the top of every page."""
    st.markdown(CSS, unsafe_allow_html=True)
    if _LOGO_BYTES:
        st.logo(_LOGO_BYTES)


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
    from lib.config import CI_CHARCOAL, CI_PURPLE
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
        f'text-transform:uppercase; letter-spacing:1px; color:{CI_CHARCOAL}; '
        f'border-bottom:2px solid {CI_PURPLE}; padding-bottom:8px; margin:32px 0 16px 0;">'
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
        f'<div style="background:white; border:1px solid {CI_LIGHT_GREY}; '
        f'border-left:4px solid {colour}; border-radius:12px; padding:18px 22px; '
        f'font-family:{FONT};">'
        f'<div style="font-size:11px; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.8px; color:{CI_GREY}; margin-bottom:8px;">{title}</div>'
        f'<div style="font-family:{FONT_DISPLAY}; font-size:30px; font-weight:700; '
        f'color:{colour}; line-height:1.1;">{value}</div>'
        f'<div style="font-size:11px; color:{CI_CHARCOAL_60}; margin-top:6px;">{subtitle}</div>'
        f"</div>"
    )

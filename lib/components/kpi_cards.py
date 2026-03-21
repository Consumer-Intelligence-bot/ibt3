"""
Standardised KPI card component.

Renders a branded metric card with title, value, subtitle, and optional
insurer/market paired layout. Editorial design: clean, authoritative.
"""

import streamlit as st

from lib.config import CI_MAGENTA, CI_GREY, CI_LIGHT_GREY, CI_NAVY, MARKET_COLOUR


def kpi_card(title: str, value: str, subtitle: str = "", colour: str | None = None):
    """Render a single KPI card as HTML."""
    if colour is None:
        colour = CI_MAGENTA
    st.markdown(
        f'<div style="'
        f'background: white;'
        f'border: 1px solid {CI_LIGHT_GREY};'
        f'border-left: 4px solid {colour};'
        f'border-radius: 2px;'
        f'padding: 18px 22px;'
        f'font-family: DM Sans, -apple-system, sans-serif;'
        f'">'
        f'<div style="font-size:11px; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.8px; color:{CI_GREY}; margin-bottom:8px;">{title}</div>'
        f'<div style="font-family:Fraunces, Georgia, serif; font-size:30px; '
        f'font-weight:700; color:{colour}; line-height:1.1;">{value}</div>'
        f'<div style="font-size:11px; color:#8B94A8; margin-top:6px;">{subtitle}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def paired_kpi_cards(
    insurer_title: str,
    insurer_value: str,
    insurer_subtitle: str,
    market_title: str,
    market_value: str,
    market_subtitle: str,
    insurer_colour: str | None = None,
    market_colour: str | None = None,
):
    """Render insurer and market KPI cards side by side."""
    col1, col2 = st.columns(2)
    with col1:
        kpi_card(insurer_title, insurer_value, insurer_subtitle, insurer_colour or CI_MAGENTA)
    with col2:
        kpi_card(market_title, market_value, market_subtitle, market_colour or MARKET_COLOUR)

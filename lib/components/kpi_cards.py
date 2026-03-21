"""
Standardised KPI card component.

Renders a branded metric card with title, value, subtitle, and optional
insurer/market paired layout.
"""

import streamlit as st

from lib.config import CI_MAGENTA, CI_GREY, CI_LIGHT_GREY, MARKET_COLOUR
from lib.formatting import FONT


def kpi_card(title: str, value: str, subtitle: str = "", colour: str | None = None):
    """Render a single KPI card as HTML."""
    if colour is None:
        colour = CI_MAGENTA
    st.markdown(
        f'<div style="background:white; border:1px solid {CI_LIGHT_GREY}; '
        f'border-top:4px solid {colour}; border-radius:4px; padding:16px 20px; '
        f'text-align:center; font-family:{FONT};">'
        f'<div style="font-size:12px; color:{CI_GREY}; margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:28px; font-weight:bold; color:{colour};">{value}</div>'
        f'<div style="font-size:11px; color:{CI_GREY}; margin-top:4px;">{subtitle}</div>'
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

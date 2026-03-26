"""
Context bar for Decision Screen layout.

Compact top bar showing screen name, insurer/market, product,
period, and sample sizes. Replaces ad-hoc st.subheader() + period banners.
"""

import streamlit as st

from lib.config import CI_CHARCOAL, CI_CHARCOAL_20, CI_CHARCOAL_60, CI_PURPLE, FONT


def render_context_bar(
    screen_name: str,
    *,
    insurer: str | None = None,
    product: str = "",
    period: str = "",
    n_insurer: int | None = None,
    n_market: int | None = None,
):
    """Render a compact context bar at the top of a Decision Screen.

    Parameters
    ----------
    screen_name : str
        Display name of the current screen (e.g. "Switching & Flows").
    insurer : str | None
        Selected insurer name, or None for market-level views.
    product : str
        Product name (Motor, Home, Pet).
    period : str
        Human-readable period label.
    n_insurer : int | None
        Insurer sample size. None to hide.
    n_market : int | None
        Market sample size. None to hide.
    """
    parts = []

    if insurer:
        parts.append(f'<span style="font-weight:700; color:{CI_PURPLE};">{insurer}</span>')
    else:
        parts.append(f'<span style="font-weight:700; color:{CI_CHARCOAL};">Market View</span>')

    if product:
        parts.append(product)
    if period:
        parts.append(period)
    if n_insurer is not None:
        parts.append(f"Insurer n={n_insurer:,}")
    if n_market is not None:
        parts.append(f"Market n={n_market:,}")

    separator = f' <span style="color:{CI_CHARCOAL_60};">&middot;</span> '
    meta_html = separator.join(parts)

    st.markdown(
        f'<div style="'
        f'background:{CI_CHARCOAL_20}; padding:10px 16px; border-radius:12px; '
        f'font-family:{FONT}; font-size:13px; color:{CI_CHARCOAL}; '
        f'margin-bottom:12px; display:flex; align-items:center; '
        f'justify-content:space-between;">'
        f'<div>'
        f'<span style="font-size:11px; font-weight:700; text-transform:uppercase; '
        f'letter-spacing:0.8px; color:{CI_CHARCOAL_60}; margin-right:12px;">'
        f'{screen_name}</span>'
        f'{meta_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

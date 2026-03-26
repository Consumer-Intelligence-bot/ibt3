"""
Display and clear cross-screen filters.

Shows active demographic and cross-screen filters with clear buttons.
"""

import streamlit as st

from lib.config import CI_GREY, CI_LIGHT_GREY, CI_MAGENTA
from lib.formatting import FONT


_FILTER_KEYS = [
    ("demographic_filter", "Demographic"),
    ("flow_filter", "Flow"),
    ("price_band_filter", "Price Band"),
    ("pcw_filter", "PCW"),
]


def render_filter_bar():
    """Show any active cross-screen filters with clear buttons."""
    active_filters = []

    for key, label in _FILTER_KEYS:
        val = st.session_state.get(key)
        if val is not None:
            active_filters.append((key, label, val))

    if not active_filters:
        return

    st.markdown(
        f'<div style="background:{CI_LIGHT_GREY}; padding:8px 16px; border-radius:12px; '
        f'font-family:{FONT}; font-size:12px; color:{CI_GREY}; margin-bottom:12px;">'
        f'<b>Active filters:</b></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(len(active_filters) + 1)
    for i, (key, label, val) in enumerate(active_filters):
        with cols[i]:
            display = _format_filter(label, val)
            if st.button(f"\u2715 {display}", key=f"clear_{key}"):
                st.session_state.pop(key, None)
                st.rerun()

    with cols[-1]:
        if st.button("Clear all filters", key="clear_all_filters"):
            for key, _, _ in active_filters:
                st.session_state.pop(key, None)
            st.rerun()


def _format_filter(label: str, val) -> str:
    """Format a filter value for display."""
    if isinstance(val, dict):
        parts = [f"{k}={v}" for k, v in val.items()]
        return f"{label}: {', '.join(parts)}"
    return f"{label}: {val}"

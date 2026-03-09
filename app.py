"""
Consumer Intelligence — Unified Streamlit Dashboard.

Combines Claims Intelligence and Shopping & Switching Intelligence
in a single multipage app. All data from Power BI via DAX queries.
"""

import streamlit as st

from lib.config import CSS
from lib.powerbi import get_token, load_months
from lib.state import format_month, init_ss_data

st.set_page_config(
    page_title="Consumer Intelligence",
    page_icon="📊",
    layout="wide",
)
st.markdown(CSS, unsafe_allow_html=True)

# ---- Header ----
st.markdown(
    '<div class="ci-header">'
    '<span class="ci-logo">Consumer Intelligence</span>'
    "</div>",
    unsafe_allow_html=True,
)

# ---- Authentication ----
token = get_token()

# ---- Load available months ----
months = load_months(token)
if len(months) < 2:
    st.warning("Fewer than 2 data months available.")
    st.stop()

# ---- Sidebar: Time window (shared by all pages) ----
with st.sidebar:
    st.markdown("### Data Controls")
    month_labels = {m: format_month(m) for m in months}
    default_start_idx = max(0, len(months) - 12)
    start_month, end_month = st.select_slider(
        "Time window",
        options=months,
        value=(months[default_start_idx], months[-1]),
        format_func=lambda x: month_labels.get(x, str(x)),
    )

# ---- Store token and time window in session state ----
st.session_state["token"] = token
st.session_state["start_month"] = start_month
st.session_state["end_month"] = end_month

# ---- Load S&S data (cached, only refreshes when time window changes) ----
init_ss_data(token, start_month, end_month)

# ---- Landing page content ----
st.markdown("## Welcome")
st.markdown(
    "Use the sidebar to navigate between **Claims Intelligence** and "
    "**Shopping & Switching Intelligence** pages."
)
st.markdown(
    f"**Data period**: {format_month(start_month)} to {format_month(end_month)}"
)

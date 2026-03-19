"""
Consumer Intelligence — Unified Streamlit Dashboard.

Combines Claims Intelligence and Shopping & Switching Intelligence
in a single multipage app. All data from Power BI via DAX queries.
"""

import signal
import sys
import threading

from dotenv import load_dotenv

load_dotenv()

import streamlit as st


# ---- Graceful shutdown handler ----
# Prevents "RuntimeError: Event loop is closed" during threading shutdown
# by catching the signal before Streamlit's default handler races with
# the asyncio event loop teardown.
# Note: signal.signal() only works from the main thread; Streamlit reruns
# page scripts in worker threads, so we must guard the call.
def _graceful_shutdown(signum, frame):
    sys.exit(0)


if threading.current_thread() is threading.main_thread() and not hasattr(
    st, "_graceful_shutdown_registered"
):
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)
    st._graceful_shutdown_registered = True

from lib.config import CSS, MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID, HOME_WORKSPACE_ID, HOME_DATASET_ID
from lib.db import clear_data, has_data
from lib.powerbi import get_token, get_main_table, get_other_table, load_months
from lib.state import format_month, init_ss_data, load_from_db

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

# ---- Authentication (persisted token survives browser refresh) ----
token = get_token()

# ---- Discover table names (auto-adapts when model is updated) ----
# Motor instance
main_table = get_main_table(token,
                            workspace_id=MOTOR_WORKSPACE_ID,
                            dataset_id=MOTOR_DATASET_ID)
other_table = get_other_table(token,
                              workspace_id=MOTOR_WORKSPACE_ID,
                              dataset_id=MOTOR_DATASET_ID)
# Home instance
home_main_table = get_main_table(token,
                                 workspace_id=HOME_WORKSPACE_ID,
                                 dataset_id=HOME_DATASET_ID)
home_other_table = get_other_table(token,
                                   workspace_id=HOME_WORKSPACE_ID,
                                   dataset_id=HOME_DATASET_ID)

# ---- Load available months (union of both products) ----
motor_months = load_months(token, main_table,
                           workspace_id=MOTOR_WORKSPACE_ID,
                           dataset_id=MOTOR_DATASET_ID)
home_months = load_months(token, home_main_table,
                          workspace_id=HOME_WORKSPACE_ID,
                          dataset_id=HOME_DATASET_ID)
months = sorted(set(motor_months) | set(home_months))
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

# ---- Store token, table names, and time window in session state ----
st.session_state["token"] = token
st.session_state["main_table"] = main_table
st.session_state["other_table"] = other_table
st.session_state["home_main_table"] = home_main_table
st.session_state["home_other_table"] = home_other_table
st.session_state["start_month"] = start_month
st.session_state["end_month"] = end_month

# ---- Load S&S data: try local DB cache first, then Power BI ----
if not st.session_state.get("data_loaded", False):
    if has_data("df_motor"):
        with st.spinner("Loading cached data..."):
            loaded = load_from_db(start_month, end_month)
        if loaded:
            st.success("Data loaded from local cache.")
            st.session_state["data_loaded"] = True
        else:
            init_ss_data(token, start_month, end_month, main_table, other_table,
                         home_main_table, home_other_table)
            st.session_state["data_loaded"] = True
    else:
        init_ss_data(token, start_month, end_month, main_table, other_table,
                     home_main_table, home_other_table)
        st.session_state["data_loaded"] = True

# ---- Clear cached data button ----
with st.sidebar:
    if st.button("Clear cached data"):
        clear_data()
        for key in ["df_motor", "dimensions", "data_loaded"]:
            st.session_state.pop(key, None)
        st.rerun()

# ---- Landing page content ----
st.markdown("## Welcome to the IBT Portal")
st.markdown(
    "Use the sidebar to navigate between pages: **Market Overview**, "
    "**Insurer Diagnostic**, **Insurer Comparison**, **Awareness**, "
    "**Claims Intelligence**, and **What Changed This Month**."
)
st.markdown(
    f"**Data period**: {format_month(start_month)} to {format_month(end_month)}"
)
st.markdown(
    "All metrics on each page use the same time period selected above. "
    "Both *versus last month* and *versus same month last year* comparisons "
    "are available on insurer pages."
)

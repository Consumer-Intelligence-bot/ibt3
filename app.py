"""
Consumer Intelligence — Unified Streamlit Dashboard.

Combines Claims Intelligence and Shopping & Switching Intelligence
in a single multipage app. Data is cached locally in DuckDB and
only re-pulled from Power BI when triggered from Admin / Governance.
"""

import signal
import sys
import threading

from dotenv import load_dotenv

load_dotenv()

import streamlit as st


# ---- Graceful shutdown handler ----
def _graceful_shutdown(signum, frame):
    sys.exit(0)


if threading.current_thread() is threading.main_thread() and not hasattr(
    st, "_graceful_shutdown_registered"
):
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)
    st._graceful_shutdown_registered = True

from lib.config import CSS
from lib.db import has_data
from lib.state import format_month, load_from_db

st.set_page_config(
    page_title="Consumer Intelligence",
    page_icon="\U0001F4CA",
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

# ---- Load data: always try DuckDB cache first ----
if not st.session_state.get("data_loaded", False):
    if has_data("df_motor"):
        with st.spinner("Loading cached data..."):
            loaded = load_from_db()
        if loaded:
            st.session_state["data_loaded"] = True
    # If no cache, we'll prompt the user to pull from Power BI via Admin page

# ---- Resolve time window from cache ----
start_month = None
end_month = None

cached_start = st.session_state.get("cached_start_month")
cached_end = st.session_state.get("cached_end_month")

if cached_start and cached_end:
    start_month = cached_start
    end_month = cached_end
else:
    # Derive from cached DataFrame if metadata was missing
    df_motor = st.session_state.get("df_motor")
    if df_motor is not None and not df_motor.empty and "RenewalYearMonth" in df_motor.columns:
        months = sorted(df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist())
        if months:
            start_month = months[max(0, len(months) - 12)]
            end_month = months[-1]

# ---- Store time window in session state ----
if start_month and end_month:
    st.session_state["start_month"] = start_month
    st.session_state["end_month"] = end_month

# ---- Landing page content ----
data_loaded = st.session_state.get("data_loaded", False)

if data_loaded:
    df_motor = st.session_state.get("df_motor")
    n_rows = len(df_motor) if df_motor is not None else 0
    n_cols = len(df_motor.columns) if df_motor is not None else 0

    period_text = ""
    if start_month and end_month:
        period_text = f"{format_month(start_month)} to {format_month(end_month)}"

    st.markdown("## Welcome to the IBT Portal")
    st.success(f"Data loaded: {n_rows:,} respondents, {n_cols} columns. Period: {period_text}")
    st.markdown(
        "Use the sidebar to navigate between pages. "
        "To refresh data from Power BI, go to **Admin / Governance** and click **Refresh from Power BI**."
    )
else:
    st.markdown("## Welcome to the IBT Portal")
    st.warning(
        "No cached data found. Go to **Admin / Governance** and click "
        "**Refresh from Power BI** to pull data."
    )
    st.markdown(
        "Once data is loaded, it is stored locally and survives server restarts. "
        "You only need to refresh when you want the latest survey data."
    )

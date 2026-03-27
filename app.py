"""
Consumer Intelligence — IBT Customer Lifecycle Dashboard.

Router-based single-page app. Uses st.session_state["active_screen"]
with conditional rendering (not st.tabs) for performance.
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

from lib.db import has_data
from lib.formatting import render_header
from lib.state import load_from_db

st.set_page_config(
    page_title="IBT3 Portal — Consumer Intelligence",
    page_icon="\U0001F4CA",
    layout="wide",
)

# Belt-and-braces font load: <link> fires before the @import in the CSS string,
# and works even if Streamlit's iframe sandbox blocks @import inside <style>.
st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)

render_header()

# ---- Load data: always try DuckDB cache first ----
if not st.session_state.get("data_loaded", False):
    if has_data("df_motor"):
        with st.spinner("Loading cached data..."):
            loaded = load_from_db()
        if loaded:
            st.session_state["data_loaded"] = True

# ---- Resolve time window from cache ----
start_month = None
end_month = None

cached_start = st.session_state.get("cached_start_month")
cached_end = st.session_state.get("cached_end_month")

if cached_start and cached_end:
    start_month = cached_start
    end_month = cached_end
else:
    df_motor = st.session_state.get("df_motor")
    if df_motor is not None and not df_motor.empty and "RenewalYearMonth" in df_motor.columns:
        months = sorted(df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist())
        if months:
            start_month = months[max(0, len(months) - 12)]
            end_month = months[-1]

if start_month and end_month:
    st.session_state["start_month"] = start_month
    st.session_state["end_month"] = end_month

# ---- Header controls + tab bar ----
from lib.components.header import render_global_controls, render_tab_bar

filters = render_global_controls()

data_loaded = st.session_state.get("data_loaded", False)

if not data_loaded:
    st.markdown("## Welcome to the IBT Portal")
    st.warning(
        "No cached data found. Go to **Admin / Governance** (sidebar) and click "
        "**Refresh from Power BI** to pull data."
    )
    # Still show admin access
    active = st.session_state.get("active_screen", "switching")
    if active == "admin":
        from screens.admin import render as render_admin
        render_admin(filters)
    st.stop()

# ---- Filter bar (show active cross-screen filters) ----
from lib.components.filter_bar import render_filter_bar
render_filter_bar()

# ---- Tab bar (only shown when data is loaded) ----
render_tab_bar()

# ---- Route to active screen ----
active = st.session_state.get("active_screen", "switching")

if active == "switching":
    from screens.switching import render as render_screen
elif active == "reasons":
    from screens.reasons import render as render_screen
elif active == "shopping":
    from screens.shopping import render as render_screen
elif active == "channels":
    from screens.channels import render as render_screen
elif active == "pre_renewal":
    from screens.pre_renewal import render as render_screen
elif active == "awareness":
    from screens.awareness import render as render_screen
elif active == "claims":
    from screens.claims import render as render_screen
elif active == "satisfaction":
    from screens.satisfaction import render as render_screen
elif active == "admin":
    from screens.admin import render as render_screen
elif active == "methodology":
    from screens.methodology import render as render_screen
elif active == "comparison":
    from screens.comparison import render as render_screen
else:
    from screens.switching import render as render_screen

render_screen(filters)

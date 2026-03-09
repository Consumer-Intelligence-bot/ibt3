"""
Customer Flows — Net flow, top sources/destinations.
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.flows import calc_net_flow, calc_top_sources, calc_top_destinations
from lib.analytics.suppression import check_suppression
from lib.config import CI_GREEN, CI_RED
from lib.state import render_global_filters, get_ss_data

st.header("Customer Flows")

filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

insurer = filters["insurer"]
if not insurer:
    st.info("Select an insurer in the sidebar.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

df_ins = apply_filters(
    df_motor, insurer=insurer, product=product, selected_months=selected_months,
    age_band=filters["age_band"], region=filters["region"], payment_type=filters["payment_type"],
)
df_mkt = apply_filters(
    df_motor, insurer=None, product=product, selected_months=selected_months,
    age_band=filters["age_band"], region=filters["region"], payment_type=filters["payment_type"],
)

sup = check_suppression(df_ins, df_mkt)
if not sup.can_show_insurer:
    st.warning(sup.message or "Insufficient data.")
    st.stop()

# ---- Net Flow ----
nf = calc_net_flow(df_mkt, insurer)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Gained", f"{nf['gained']:,}")
with col2:
    st.metric("Lost", f"{nf['lost']:,}")
with col3:
    st.metric("Net", f"{nf['net']:+,}")

# ---- Sources / Destinations ----
col_src, col_dst = st.columns(2)

with col_src:
    st.subheader("Gaining From")
    src = calc_top_sources(df_mkt, insurer, 10)
    if len(src) > 0:
        src = src.sort_values(ascending=True)
        fig = go.Figure(go.Bar(x=src.values, y=src.index, orientation="h", marker_color=CI_GREEN))
        fig.update_layout(height=max(250, len(src) * 25), margin=dict(l=150, t=10),
                          font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No source data.")

with col_dst:
    st.subheader("Losing To")
    dst = calc_top_destinations(df_mkt, insurer, 10)
    if len(dst) > 0:
        dst = dst.sort_values(ascending=True)
        fig = go.Figure(go.Bar(x=dst.values, y=dst.index, orientation="h", marker_color=CI_RED))
        fig.update_layout(height=max(250, len(dst) * 25), margin=dict(l=150, t=10),
                          font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No destination data.")

"""
Price Sensitivity — Price direction distribution.
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.price import calc_price_direction_dist
from lib.analytics.suppression import check_suppression
from lib.config import CI_GREY, CI_MAGENTA
from lib.state import render_global_filters, get_ss_data

st.header("Price Sensitivity")

filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

insurer = filters["insurer"]
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
dist_ins = calc_price_direction_dist(df_ins) if insurer and sup.can_show_insurer else None
dist_mkt = calc_price_direction_dist(df_mkt)

if dist_mkt is not None and len(dist_mkt) > 0:
    fig = go.Figure()
    if dist_ins is not None and len(dist_ins) > 0:
        fig.add_trace(go.Bar(name="Your Customers", x=dist_ins.index, y=dist_ins.values, marker_color=CI_MAGENTA))
    fig.add_trace(go.Bar(name="Market", x=dist_mkt.index, y=dist_mkt.values, marker_color=CI_GREY))
    fig.update_layout(
        barmode="group", font=dict(family="Verdana"),
        title="Price Direction Distribution",
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Price data not available.")

"""
Channel & PCW Analysis — Quote-to-buy mismatch and channel usage.
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.channels import calc_channel_usage, calc_quote_buy_mismatch
from lib.analytics.demographics import apply_filters
from lib.analytics.suppression import check_suppression
from lib.config import CI_MAGENTA
from lib.state import render_global_filters, get_ss_data

st.header("Channel & PCW")

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

# ---- Quote-to-Buy Mismatch ----
col1, col2 = st.columns(2)

with col1:
    st.subheader("Quote-to-Buy Mismatch")
    mis_ins = calc_quote_buy_mismatch(df_ins, df_questions) if insurer and sup.can_show_insurer else None
    mis_mkt = calc_quote_buy_mismatch(df_mkt, df_questions)
    if mis_mkt is not None:
        st.metric("Market Mismatch", f"{mis_mkt:.1%}")
        if mis_ins is not None:
            st.metric(f"{insurer} Mismatch", f"{mis_ins:.1%}")
    else:
        st.info("Mismatch data not available.")

with col2:
    st.subheader("Channel Usage")
    ch_data = df_ins if insurer and sup.can_show_insurer else df_mkt
    ch = calc_channel_usage(ch_data, df_questions)
    if ch is not None and len(ch) > 0:
        fig = go.Figure(go.Bar(x=ch.values, y=ch.index, orientation="h", marker_color=CI_MAGENTA))
        fig.update_layout(
            height=max(250, len(ch) * 25), margin=dict(l=150, t=10),
            font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Channel data not available.")

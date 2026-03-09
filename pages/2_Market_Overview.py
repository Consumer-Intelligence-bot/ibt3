"""
Market Overview — Shopping & Switching Intelligence.
Market-level KPIs, trends, top reasons, and channels.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.channels import calc_channel_usage, calc_pcw_usage
from lib.analytics.demographics import apply_filters
from lib.analytics.rates import calc_shopping_rate, calc_switching_rate, calc_retention_rate
from lib.analytics.reasons import calc_reason_ranking
from lib.config import CI_GREEN, CI_MAGENTA, CI_GREY, MIN_BASE_REASON
from lib.state import format_year_month, render_global_filters, get_ss_data

st.header("Market Overview")

# ---- Global filters ----
filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded. Check Power BI connection.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

df_market = apply_filters(df_motor, product=product, selected_months=selected_months)
n = len(df_market)

if n == 0:
    st.warning("No data for selected filters.")
    st.stop()

# ---- KPIs ----
shop = calc_shopping_rate(df_market)
switch = calc_switching_rate(df_market)
retain = calc_retention_rate(df_market)

min_ym = df_market["RenewalYearMonth"].min() if "RenewalYearMonth" in df_market.columns else None
max_ym = df_market["RenewalYearMonth"].max() if "RenewalYearMonth" in df_market.columns else None
period_label = "—"
if pd.notna(min_ym) and pd.notna(max_ym):
    period_label = f"{format_year_month(min_ym)} to {format_year_month(max_ym)}"

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Shopping Rate", f"{shop:.0%}" if shop else "—")
with col2:
    st.metric("Switching Rate", f"{switch:.0%}" if switch else "—")
with col3:
    st.metric("Retention Rate", f"{retain:.0%}" if retain else "—")
with col4:
    st.metric("Data Period", period_label)
    st.caption(f"n = {n:,}")

# ---- Retention trend ----
st.subheader(f"Market Retention Trend — {period_label}")
by_month = df_market.groupby("RenewalYearMonth").agg(
    retained=("IsRetained", "sum"),
    total=("UniqueID", "count"),
).reset_index()
by_month["retention"] = by_month["retained"] / by_month["total"]
by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)

fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(
    x=by_month["month_label"], y=by_month["retention"],
    mode="lines+markers",
    line=dict(color=CI_MAGENTA, width=2.5),
    marker=dict(size=6),
    hovertemplate="Retention: %{y:.1%}<br>%{x}<extra></extra>",
))
fig_trend.update_layout(
    yaxis_tickformat=".0%", yaxis_title="Retention Rate",
    font=dict(family="Verdana"), height=400,
    plot_bgcolor="white", paper_bgcolor="white",
)
col_left, col_right = st.columns(2)
with col_left:
    st.plotly_chart(fig_trend, use_container_width=True)

# ---- Why Customers Shop (Q8) ----
with col_right:
    st.subheader("Why Customers Shop (Q8)")
    n_shoppers = df_market["IsShopper"].sum() if "IsShopper" in df_market.columns else 0
    if n_shoppers < MIN_BASE_REASON:
        st.info(f"Insufficient shoppers ({n_shoppers}) for reason analysis (minimum {MIN_BASE_REASON}).")
    elif not df_questions.empty:
        why = calc_reason_ranking(df_market, df_questions, "Q8", top_n=5)
        if why:
            why_df = pd.DataFrame(why)
            fig_why = go.Figure(go.Bar(
                x=why_df["rank1_pct"], y=why_df["reason"], orientation="h",
                marker_color=CI_MAGENTA,
                text=[f"{p:.0%}" for p in why_df["rank1_pct"]],
                textposition="outside",
            ))
            fig_why.update_layout(
                xaxis_tickformat=".0%", height=250,
                margin=dict(l=200, t=10), font=dict(family="Verdana"),
                plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig_why, use_container_width=True)
        else:
            st.info("No Q8 data available.")
    else:
        st.info("Question data not available.")

# ---- Channel usage & PCW ----
col_ch, col_pcw = st.columns(2)

with col_ch:
    st.subheader("Shopping Channels")
    ch = calc_channel_usage(df_market, df_questions)
    if ch is not None and len(ch) > 0:
        ch = ch.head(8)
        fig_ch = go.Figure(go.Bar(
            x=ch.values, y=ch.index, orientation="h",
            marker_color=CI_GREEN,
            text=[f"{v:.0%}" for v in ch.values],
            textposition="outside",
        ))
        fig_ch.update_layout(
            xaxis_tickformat=".0%", height=250,
            margin=dict(l=150, t=10), font=dict(family="Verdana"),
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_ch, use_container_width=True)
    else:
        st.info("Channel data not available.")

with col_pcw:
    st.subheader("PCW Market Share")
    pcw = calc_pcw_usage(df_market, df_questions)
    if pcw is not None and len(pcw) > 0:
        fig_pcw = go.Figure(go.Pie(
            labels=pcw.index, values=pcw.values, hole=0.4,
            textinfo="label+percent",
            marker=dict(line=dict(color="white", width=2)),
        ))
        fig_pcw.update_layout(height=250, margin=dict(t=10), font=dict(family="Verdana"))
        st.plotly_chart(fig_pcw, use_container_width=True)
    else:
        st.info("PCW data not available.")

# ---- Footer ----
st.caption(f"Data period: {period_label} | n = {n:,} | \u00a9 Consumer Intelligence 2026")

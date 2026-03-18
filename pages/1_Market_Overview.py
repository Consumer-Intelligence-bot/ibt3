"""
Market Overview — Shopping & Switching Intelligence (Public).
Market-level KPIs, trends, top reasons, and channels.

This is a PUBLIC page: NO insurer names must appear anywhere,
including hover text, axis labels, or chart annotations.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.channels import calc_channel_usage, calc_pcw_usage
from lib.analytics.demographics import apply_filters
from lib.analytics.rates import calc_shopping_rate, calc_switching_rate, calc_retention_rate, calc_rolling_avg
from lib.analytics.reasons import calc_reason_ranking
from lib.chart_export import apply_export_metadata
from lib.config import CI_GREEN, CI_MAGENTA, CI_GREY, MIN_BASE_REASON
from lib.question_ref import get_question_text
from lib.state import format_year_month, render_global_filters, get_ss_data

FONT = "Verdana, Geneva, sans-serif"

st.header("Market Overview")

# ---- Global filters (product + period affect all visuals) ----
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

# ---- Derive period label ----
min_ym = df_market["RenewalYearMonth"].min() if "RenewalYearMonth" in df_market.columns else None
max_ym = df_market["RenewalYearMonth"].max() if "RenewalYearMonth" in df_market.columns else None
period_label = "\u2014"
if pd.notna(min_ym) and pd.notna(max_ym):
    period_label = f"{format_year_month(min_ym)} to {format_year_month(max_ym)}"

# ---- Active period banner ----
st.markdown(
    f'<div style="background:#F2F2F2; border-left:4px solid {CI_MAGENTA}; '
    f'padding:10px 16px; margin-bottom:16px; font-family:{FONT}; font-size:14px; '
    f'color:#333;">'
    f'<b>Active period:</b> {period_label} &nbsp;|&nbsp; '
    f'<b>Product:</b> {product or "All"} &nbsp;|&nbsp; '
    f'<b>Base:</b> n\u2009=\u2009{n:,}'
    f'</div>',
    unsafe_allow_html=True,
)

# ---- KPI cards ----
shop = calc_shopping_rate(df_market)
switch = calc_switching_rate(df_market)
retain = calc_retention_rate(df_market)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Shopping Rate", f"{shop:.0%}" if shop else "\u2014")
with col2:
    st.metric("Switching Rate", f"{switch:.0%}" if switch else "\u2014")
with col3:
    st.metric("Retention Rate", f"{retain:.0%}" if retain else "\u2014")
with col4:
    st.metric("Data Period", period_label)
    st.caption(f"n = {n:,}")

# ---- Market Retention Trend ----
st.subheader("Market Retention Trend")
st.caption(get_question_text("Q15"))

use_rolling = st.toggle("Rolling 3-month average", value=True)

by_month = df_market.groupby("RenewalYearMonth").agg(
    retained=("IsRetained", "sum"),
    total=("UniqueID", "count"),
).reset_index()
by_month = by_month.sort_values("RenewalYearMonth")
by_month["retention"] = by_month["retained"] / by_month["total"]
by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)

if use_rolling:
    by_month = calc_rolling_avg(by_month, window=3, rate_col="retention")
    plot_col = "retention_rolling"
    chart_title = "Market Retention Trend (Rolling 3-month average)"
else:
    plot_col = "retention"
    chart_title = "Market Retention Trend (Monthly)"

fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(
    x=by_month["month_label"],
    y=by_month[plot_col],
    mode="lines+markers",
    line=dict(color=CI_MAGENTA, width=2.5),
    marker=dict(size=6, color=CI_MAGENTA),
    hovertemplate="Retention: %{y:.1%}<br>%{x}<extra></extra>",
))
fig_trend.update_layout(
    yaxis_tickformat=".0%",
    yaxis_title="Retention Rate",
    font=dict(family=FONT),
    height=420,
    margin=dict(l=60, r=30, t=50, b=80),
    plot_bgcolor="white",
    paper_bgcolor="white",
)
apply_export_metadata(
    fig_trend,
    title=chart_title,
    period=period_label,
    base=n,
    question="Q15",
    subtitle="Rolling 3-month average" if use_rolling else "Monthly retention rate across all insurers",
)
st.plotly_chart(fig_trend, use_container_width=True)

# ---- Why Customers Shop (Q8) & Shopping Channels (Q9b) ----
col_left, col_right = st.columns(2)

# -- Q8 Reasons --
with col_left:
    st.subheader("Why Customers Shop (Q8)")
    st.caption(get_question_text("Q8"))
    n_shoppers = int(df_market["IsShopper"].sum()) if "IsShopper" in df_market.columns else 0

    if n_shoppers < MIN_BASE_REASON:
        st.info(
            f"Insufficient shoppers ({n_shoppers}) for reason analysis "
            f"(minimum {MIN_BASE_REASON})."
        )
    elif not df_questions.empty:
        why = calc_reason_ranking(df_market, df_questions, "Q8", top_n=5)
        if why:
            why_df = pd.DataFrame(why)
            fig_why = go.Figure(go.Bar(
                x=why_df["rank1_pct"],
                y=why_df["reason"],
                orientation="h",
                marker_color=CI_MAGENTA,
                text=[f"{p:.0%}" for p in why_df["rank1_pct"]],
                textposition="outside",
                hovertemplate="%{y}: %{x:.1%}<extra></extra>",
            ))
            fig_why.update_layout(
                xaxis_tickformat=".0%",
                height=300,
                margin=dict(l=200, r=30, t=50, b=80),
                font=dict(family=FONT),
                plot_bgcolor="white",
                paper_bgcolor="white",
            )
            apply_export_metadata(
                fig_why,
                title="Why Customers Shop — Top 5 Reasons",
                period=period_label,
                base=n_shoppers,
                question="Q8",
            )
            st.plotly_chart(fig_why, use_container_width=True)
        else:
            st.info("No Q8 data available.")
    else:
        st.info("Question data not available.")

# -- Channel usage (Q9b) --
with col_right:
    st.subheader("Shopping Channels (Q9b)")
    st.caption(get_question_text("Q9b"))
    ch = calc_channel_usage(df_market, df_questions)
    if ch is not None and len(ch) > 0:
        # Sort descending and take top channels
        ch = ch.sort_values(ascending=True)  # ascending for horizontal bar layout
        fig_ch = go.Figure(go.Bar(
            x=ch.values,
            y=ch.index,
            orientation="h",
            marker_color=CI_GREEN,
            text=[f"{v:.0%}" for v in ch.values],
            textposition="outside",
            hovertemplate="%{y}: %{x:.1%}<extra></extra>",
        ))
        fig_ch.update_layout(
            xaxis_tickformat=".0%",
            height=300,
            margin=dict(l=150, r=30, t=50, b=80),
            font=dict(family=FONT),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        apply_export_metadata(
            fig_ch,
            title="Shopping Channels",
            period=period_label,
            base=n_shoppers if n_shoppers > 0 else n,
            question="Q9b",
        )
        st.plotly_chart(fig_ch, use_container_width=True)
    else:
        st.info("Channel data not available.")

# ---- PCW Market Share (Q11) ----
st.subheader("PCW Market Share (Q11)")
st.caption(get_question_text("Q11"))
pcw = calc_pcw_usage(df_market, df_questions)
if pcw is not None and len(pcw) > 0:
    col_pcw, _ = st.columns([2, 1])
    with col_pcw:
        fig_pcw = go.Figure(go.Pie(
            labels=pcw.index,
            values=pcw.values,
            hole=0.4,
            textinfo="label+percent",
            hovertemplate="%{label}: %{percent}<extra></extra>",
            marker=dict(line=dict(color="white", width=2)),
        ))
        fig_pcw.update_layout(
            height=380,
            margin=dict(l=30, r=30, t=50, b=80),
            font=dict(family=FONT),
        )
        apply_export_metadata(
            fig_pcw,
            title="PCW Market Share",
            period=period_label,
            base=n_shoppers if n_shoppers > 0 else n,
            question="Q11",
        )
        st.plotly_chart(fig_pcw, use_container_width=True)
else:
    st.info("PCW data not available.")

# ---- Footer ----
st.caption(
    f"Data period: {period_label} | n = {n:,} | "
    f"\u00a9 Consumer Intelligence 2026"
)

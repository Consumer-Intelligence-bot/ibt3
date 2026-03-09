"""
Brand Awareness — Market View.
Rank and rates across the market over time.
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.awareness import (
    Q1_GATING_MESSAGE,
    calc_awareness_bump,
    calc_awareness_rates,
    calc_awareness_summary,
)
from lib.analytics.demographics import apply_filters
from lib.config import CI_GREEN, CI_GREY, CI_RED, BUMP_COLOURS
from lib.state import format_year_month, render_global_filters, get_ss_data

st.header("Brand Awareness \u2014 Market View")

filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

# ---- Level toggle ----
level = st.radio(
    "Awareness level",
    ["prompted", "consideration"],
    format_func=lambda x: {"prompted": "Prompted (Q2)", "consideration": "Consideration (Q27)"}.get(x, x),
    horizontal=True,
)

df_main = apply_filters(df_motor, product=product, selected_months=selected_months)

# ---- KPI summary ----
summary = calc_awareness_summary(df_main, df_questions, level)
if summary is None:
    st.warning("No awareness data available for this selection.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Brands Eligible", f"{summary['n_brands']:,}")
with col2:
    st.metric("Market Average", f"{summary['mean_rate']:.1%}")
with col3:
    st.metric("Highest", f"{summary['top_brand_rate']:.1%}")
    st.caption(summary["top_brand_name"])
with col4:
    if summary.get("most_improved_name"):
        change = summary["most_improved_change"]
        sign = "+" if change > 0 else ""
        st.metric("Most Improved", f"{summary['most_improved_name']}")
        st.caption(f"{sign}{change:.1%}")
    else:
        st.metric("Most Improved", "\u2014")

# ---- Bump chart ----
st.subheader("Brand Rank Over Time")
bump_data = calc_awareness_bump(df_main, df_questions, level)
if bump_data.empty:
    st.info("Insufficient data for bump chart.")
else:
    bump_data["month_label"] = bump_data["month"].apply(format_year_month)
    brands = sorted(bump_data["brand"].unique())

    fig = go.Figure()
    for i, brand in enumerate(brands):
        bd = bump_data[bump_data["brand"] == brand].sort_values("month")
        colour = BUMP_COLOURS[i % len(BUMP_COLOURS)]
        fig.add_trace(go.Scatter(
            x=bd["month_label"], y=bd["rank"],
            mode="lines+markers", name=brand,
            line=dict(color=colour, width=2), marker=dict(size=6, color=colour),
            hovertemplate=f"<b>{brand}</b><br>Rank: %{{y}}<br>Rate: %{{text}}<br>%{{x}}<extra></extra>",
            text=[f"{r:.1%}" for r in bd["rate"]],
        ))
    fig.update_layout(
        yaxis=dict(autorange="reversed", title="Rank", dtick=1),
        height=500, font=dict(family="Verdana"),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.15),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---- Ranked bar chart ----
st.subheader("Awareness Rate \u2014 Latest Month")
rates = calc_awareness_rates(df_main, df_questions, level)
if rates.empty:
    st.info("Insufficient data for bar chart.")
else:
    latest_month = rates["month"].max()
    latest = rates[rates["month"] == latest_month].sort_values("rate", ascending=True)
    market_avg = latest["rate"].mean()

    bar_colours = [CI_GREEN if r > market_avg else CI_RED for r in latest["rate"]]
    fig_bar = go.Figure(go.Bar(
        y=latest["brand"], x=latest["rate"], orientation="h",
        marker_color=bar_colours,
        text=[f"{r:.1%}" for r in latest["rate"]],
        textposition="outside",
    ))
    fig_bar.add_vline(
        x=market_avg, line_dash="dash", line_color=CI_GREY, line_width=1.5,
        annotation_text=f"Market avg: {market_avg:.1%}",
        annotation_font_size=11, annotation_font_color=CI_GREY,
    )
    fig_bar.update_layout(
        xaxis_tickformat=".0%", height=max(400, len(latest) * 30),
        margin=dict(l=150), font=dict(family="Verdana"),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

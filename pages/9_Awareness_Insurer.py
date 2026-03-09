"""
Brand Awareness — Insurer View.
Slopegraph panels and trend lines with market percentile band.
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.awareness import (
    Q1_GATING_MESSAGE,
    calc_awareness_market_bands,
    calc_awareness_rates,
    calc_awareness_slopegraph,
)
from lib.analytics.demographics import apply_filters
from lib.config import CI_BLUE, CI_GREEN, CI_GREY, CI_MAGENTA
from lib.state import format_year_month, render_global_filters, get_ss_data

st.header("Brand Awareness \u2014 Insurer View")

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
df_main = apply_filters(df_motor, product=product, selected_months=selected_months)

# ---- Slopegraph panels ----
st.subheader("Awareness Funnel")
prompted_slope = calc_awareness_slopegraph(df_main, df_questions, insurer, "prompted")
consideration_slope = calc_awareness_slopegraph(df_main, df_questions, insurer, "consideration")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Spontaneous (Q1)**")
    st.info(Q1_GATING_MESSAGE)

for col, title, data, colour in [
    (col2, "Prompted (Q2)", prompted_slope, CI_BLUE),
    (col3, "Consideration (Q27)", consideration_slope, CI_GREEN),
]:
    with col:
        st.markdown(f"**{title}**")
        if data and data.get("can_show"):
            arrows = {"up": "\u2191", "down": "\u2193", "flat": "\u2192"}
            arrow = arrows.get(data["direction"], "\u2192")
            delta_sign = "+" if data["change"] > 0 else ""

            st.metric(
                format_year_month(data["start_month"]),
                f"{data['start_rate']:.1%}",
            )
            st.markdown(f"### {arrow}")
            st.metric(
                format_year_month(data["end_month"]),
                f"{data['end_rate']:.1%}",
                delta=f"{delta_sign}{data['change']:.1%}",
            )
            # Market context
            if data.get("start_market_rate") is not None:
                st.caption(f"Market: {data['start_market_rate']:.1%} \u2192 {data['end_market_rate']:.1%}")
        else:
            st.info("Insufficient data")

# ---- Trend chart with market bands ----
st.subheader("Awareness Trend vs Market")

prompted_rates = calc_awareness_rates(df_main, df_questions, "prompted")
consideration_rates = calc_awareness_rates(df_main, df_questions, "consideration")
prompted_bands = calc_awareness_market_bands(df_main, df_questions, "prompted")
consideration_bands = calc_awareness_market_bands(df_main, df_questions, "consideration")

fig = go.Figure()

# Market percentile bands
for bands_df, band_colour, band_label in [
    (prompted_bands, "rgba(91, 194, 231, 0.15)", "Market 25th\u201375th (Prompted)"),
    (consideration_bands, "rgba(72, 162, 63, 0.15)", "Market 25th\u201375th (Consideration)"),
]:
    if not bands_df.empty:
        months_label = [format_year_month(m) for m in bands_df["month"]]
        fig.add_trace(go.Scatter(
            x=months_label, y=bands_df["p75"],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=months_label, y=bands_df["p25"],
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor=band_colour, name=band_label, hoverinfo="skip", showlegend=False,
        ))

# Insurer lines
for level, rates_df, colour, label in [
    ("prompted", prompted_rates, CI_BLUE, "Prompted"),
    ("consideration", consideration_rates, CI_GREEN, "Consideration"),
]:
    if rates_df.empty:
        continue
    brand_data = rates_df[rates_df["brand"] == insurer].sort_values("month")
    if brand_data.empty:
        continue
    x = [format_year_month(m) for m in brand_data["month"]]
    fig.add_trace(go.Scatter(
        x=x, y=brand_data["rate"],
        mode="lines+markers", name=label,
        line=dict(color=colour, width=2.5),
        marker=dict(size=6, color=colour),
        hovertemplate=f"<b>{label}</b><br>Rate: %{{y:.1%}}<br>%{{x}}<extra></extra>",
    ))

fig.update_layout(
    yaxis_tickformat=".0%", yaxis_title="Awareness Rate", yaxis_range=[0, 1],
    legend=dict(orientation="h", yanchor="top", y=-0.12),
    height=400, font=dict(family="Verdana"),
    plot_bgcolor="white", paper_bgcolor="white",
)
st.plotly_chart(fig, use_container_width=True)

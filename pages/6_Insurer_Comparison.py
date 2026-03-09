"""
Insurer Comparison — Side-by-side retention with CI whiskers.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.confidence import ConfidenceLabel, MetricType, assess_confidence
from lib.analytics.demographics import apply_filters
from lib.analytics.flows import calc_net_flow
from lib.analytics.rates import calc_retention_rate, calc_shopping_rate
from lib.analytics.trends import calc_trend
from lib.config import CI_GREEN, CI_GREY, CI_RED, CI_YELLOW, SYSTEM_FLOOR_N
from lib.state import render_global_filters, get_ss_data

st.header("Insurer Comparison")

filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

df_mkt = apply_filters(
    df_motor, product=product, selected_months=selected_months,
    age_band=filters["age_band"], region=filters["region"], payment_type=filters["payment_type"],
)
market_ret = calc_retention_rate(df_mkt)

# Insurer multi-select
all_insurers = []
if "DimInsurer" in dimensions:
    all_insurers = sorted(dimensions["DimInsurer"]["Insurer"].dropna().astype(str).tolist())

selected_insurers = st.multiselect("Filter to specific insurers (optional)", all_insurers)
insurers = selected_insurers if selected_insurers else all_insurers

# ---- Compute metrics per insurer ----
rows = []
for ins in insurers:
    df_ins = apply_filters(
        df_motor, insurer=ins, product=product, selected_months=selected_months,
        age_band=filters["age_band"], region=filters["region"], payment_type=filters["payment_type"],
    )
    n = len(df_ins)
    if n < SYSTEM_FLOOR_N:
        continue

    existing = df_ins[~df_ins["IsNewToMarket"]]
    retained = existing["IsRetained"].sum()
    total = len(existing)
    if total == 0:
        continue

    bay = bayesian_smooth_rate(int(retained), total, market_ret or 0.5)
    ci_w = (bay["ci_upper"] - bay["ci_lower"]) * 100
    conf = assess_confidence(n, bay["posterior_mean"], MetricType.RATE, posterior_ci_width=ci_w)

    if conf.label == ConfidenceLabel.INSUFFICIENT:
        continue

    shopping = calc_shopping_rate(df_ins)
    nf = calc_net_flow(df_mkt, ins)
    trend = calc_trend(df_ins, market_ret or 0.5)
    trend_dir = trend["direction"] if not trend["suppressed"] else None

    rows.append({
        "Insurer": ins, "n": total,
        "retention": bay["posterior_mean"],
        "ci_lower": bay["ci_lower"], "ci_upper": bay["ci_upper"],
        "ci_width": ci_w, "shopping": shopping,
        "net_flow": nf["net"], "confidence": conf.label.value,
        "trend_dir": trend_dir,
    })

if not rows:
    st.warning("No insurers meet the threshold for this selection.")
    st.stop()

df_tbl = pd.DataFrame(rows).sort_values("retention", ascending=False)

# ---- Retention bar chart ----
st.subheader("Retention by Insurer")

colours = [CI_GREEN if r > (market_ret or 0) else CI_RED for r in df_tbl["retention"]]
fig = go.Figure(go.Bar(
    x=df_tbl["retention"], y=df_tbl["Insurer"], orientation="h",
    marker_color=colours,
    text=[f"{r:.1%}" for r in df_tbl["retention"]],
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>Retention: %{x:.1%}<extra></extra>",
))
# CI whiskers
for i, row in df_tbl.iterrows():
    fig.add_trace(go.Scatter(
        x=[row["ci_lower"], row["ci_upper"]],
        y=[row["Insurer"], row["Insurer"]],
        mode="lines", line=dict(color=CI_GREY, width=2),
        showlegend=False, hoverinfo="skip",
    ))

if market_ret:
    fig.add_vline(
        x=market_ret, line_dash="dash", line_color=CI_GREY, line_width=1.5,
        annotation_text=f"Market: {market_ret:.1%}",
        annotation_font_size=11, annotation_font_color=CI_GREY,
    )

fig.update_layout(
    xaxis_tickformat=".0%", yaxis=dict(autorange="reversed"),
    height=max(400, len(df_tbl) * 35), margin=dict(l=150),
    font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white",
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

# ---- Metrics table ----
st.subheader("Metrics Summary")

_TREND_ARROWS = {"up": "\u25B2", "down": "\u25BC", "stable": "\u25CF"}
display = df_tbl.copy()
display["Retention"] = display["retention"].apply(lambda x: f"{x:.1%}")
display["Shopping Rate"] = display["shopping"].apply(lambda x: f"{x:.1%}" if x else "\u2014")
display["Net Flow"] = display["net_flow"].apply(lambda x: f"{x:+,}" if x else "\u2014")
display["Trend"] = display["trend_dir"].apply(lambda x: _TREND_ARROWS.get(x, "\u2014") if x else "\u2014")
display["Confidence"] = display["confidence"]
display["Renewals"] = display["n"].apply(lambda x: f"{x:,}")
display = display[["Insurer", "Renewals", "Retention", "Shopping Rate", "Net Flow", "Trend", "Confidence"]]

st.dataframe(display, use_container_width=True, hide_index=True)

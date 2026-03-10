"""
Claims Intelligence — Motor Insurance.
Satisfaction analysis from Q52/Q53 with AI-generated narrative.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.config import (
    CI_BLUE, CI_DARK, CI_GREEN, CI_LGREY, CI_RED, CI_VIOLET, CI_WHITE,
    MIN_BASE_INDICATIVE, Z_95,
)
from lib.narrative import generate_claims_narrative
from lib.powerbi import load_q52, load_q53
from lib.state import format_month

st.markdown(
    f'<h1 style="color:{CI_VIOLET}; margin-top:0;">'
    "Claims Intelligence | Motor Insurance</h1>",
    unsafe_allow_html=True,
)

# ---- Get shared state ----
token = st.session_state.get("token")
start_month = st.session_state.get("start_month")
end_month = st.session_state.get("end_month")
main_table = st.session_state.get("main_table", "MainData")
other_table = st.session_state.get("other_table", "AllOtherData")

if not token or not start_month or not end_month:
    st.warning("Please authenticate on the main page first.")
    st.stop()

# ---- Load Claims data ----
q52_df = load_q52(token, start_month, end_month, main_table, other_table)
q53_df = load_q53(token, start_month, end_month, main_table, other_table)

if q52_df.empty:
    st.warning("No claims data returned for this period.")
    st.stop()

for col in ["Q52_n", "Q52_mean", "Q52_std"]:
    if col in q52_df.columns:
        q52_df[col] = pd.to_numeric(q52_df[col], errors="coerce")

# ---- Market averages ----
eligible = q52_df[q52_df["Q52_n"] >= MIN_BASE_INDICATIVE].copy()
if eligible.empty:
    st.warning("No insurers meet the minimum sample size requirement.")
    st.stop()

total_n = eligible["Q52_n"].sum()
market_mean = (eligible["Q52_mean"] * eligible["Q52_n"]).sum() / total_n
all_eligible_means = eligible["Q52_mean"].tolist()

# ---- Insurer selector (shared across all tabs via session_state key) ----
insurer_list = sorted(eligible["CurrentCompany"].dropna().unique().tolist())
all_options = [""] + insurer_list

# Validate saved value still exists in options
if "selected_insurer" in st.session_state and st.session_state["selected_insurer"] not in all_options:
    st.session_state["selected_insurer"] = ""

selected_insurer = st.sidebar.selectbox(
    "Insurer", all_options,
    format_func=lambda x: x or "All / Market",
    key="selected_insurer",
)

# ---- Insurer data ----
if not selected_insurer:
    st.info("Select an insurer in the sidebar to see detailed claims analysis.")
    st.stop()

ins_row = q52_df[q52_df["CurrentCompany"] == selected_insurer]
if ins_row.empty:
    st.warning(f"No data for {selected_insurer} in the selected period.")
    st.stop()

ins_row = ins_row.iloc[0]
ins_n = int(ins_row["Q52_n"])
ins_mean = float(ins_row["Q52_mean"])
ins_std = float(ins_row["Q52_std"]) if pd.notna(ins_row["Q52_std"]) else 0.0


def confidence_interval(mean, std, n):
    if n < 1 or std is None or np.isnan(std):
        return (None, None)
    margin = Z_95 * std / np.sqrt(n)
    return (round(mean - margin, 3), round(mean + margin, 3))


def confidence_tier(n, ci_width):
    if n < 30:
        return "INSUFFICIENT"
    if n < 50:
        return "LOW"
    if n >= 90 and ci_width <= 0.25:
        return "HIGH"
    if n >= 50 and ci_width <= 0.35:
        return "MEDIUM"
    return "LOW"


def assign_stars(insurer_mean, all_means):
    if not all_means or insurer_mean is None:
        return None
    sorted_means = sorted(all_means)
    n = len(sorted_means)
    rank = sum(m <= insurer_mean for m in sorted_means)
    percentile = rank / n
    if percentile >= 0.80:
        return 5
    elif percentile >= 0.60:
        return 4
    elif percentile >= 0.40:
        return 3
    elif percentile >= 0.20:
        return 2
    else:
        return 1


def gap_colour(gap):
    if gap > 0.1:
        return CI_GREEN
    elif gap < -0.1:
        return CI_RED
    return CI_DARK


def tier_colour(tier):
    return {"HIGH": CI_GREEN, "MEDIUM": CI_BLUE, "LOW": "#FFCD00", "INSUFFICIENT": CI_RED}.get(tier, CI_DARK)


ci_lo, ci_hi = confidence_interval(ins_mean, ins_std, ins_n)
ci_w = (ci_hi - ci_lo) if ci_lo is not None and ci_hi is not None else 999
tier = confidence_tier(ins_n, ci_w)
gap = ins_mean - market_mean
stars = assign_stars(ins_mean, all_eligible_means)

if ins_n < MIN_BASE_INDICATIVE:
    st.error(f"Insufficient data for {selected_insurer}. Minimum 30 claimants required.")
    st.stop()

# ---- AI Narrative ----
# Build diagnostic data for narrative
diagnostics_for_ai = None
if not q53_df.empty:
    for col in ["Q53_n", "Q53_mean", "Q53_std", "Ranking"]:
        if col in q53_df.columns:
            q53_df[col] = pd.to_numeric(q53_df[col], errors="coerce")

    eligible_companies = set(eligible["CurrentCompany"].tolist())
    q53_eligible = q53_df[
        (q53_df["CurrentCompany"].isin(eligible_companies))
        & (q53_df["Q53_n"] >= MIN_BASE_INDICATIVE)
    ]
    market_q53 = (
        q53_eligible.groupby("Subject")
        .apply(
            lambda g: pd.Series({
                "market_mean": (g["Q53_mean"] * g["Q53_n"]).sum() / g["Q53_n"].sum(),
            }),
            include_groups=False,
        )
        .reset_index()
    )
    ins_q53 = q53_df[q53_df["CurrentCompany"] == selected_insurer].copy()
    if not ins_q53.empty and not market_q53.empty:
        diag = ins_q53.merge(market_q53, on="Subject")
        diag = diag[diag["Q53_n"] >= MIN_BASE_INDICATIVE]
        if not diag.empty:
            diagnostics_for_ai = [
                {
                    "subject": row["Subject"],
                    "ins_mean": row["Q53_mean"],
                    "mkt_mean": row["market_mean"],
                    "gap": row["Q53_mean"] - row["market_mean"],
                }
                for _, row in diag.iterrows()
            ]

narrative = generate_claims_narrative(
    selected_insurer, ins_mean, market_mean, gap, stars, diagnostics_for_ai
)

if narrative:
    st.markdown(f"### {narrative['headline']}")
    st.markdown(f"*{narrative['subtitle']}*")
    st.markdown(narrative["paragraph"])
    st.markdown("---")

# ---- Confidence Banner ----
st.markdown('<div class="section-title">Data Confidence</div>', unsafe_allow_html=True)
t_col = tier_colour(tier)
st.markdown(
    f'<div style="padding:12px; border-left:4px solid {t_col}; '
    f'background:{CI_LGREY}; margin-bottom:16px;">'
    f"<strong>{selected_insurer}</strong> &mdash; "
    f"<strong style='color:{t_col}'>{tier}</strong> confidence &nbsp;|&nbsp; "
    f"<strong>{ins_n:,}</strong> claimant responses"
    f"</div>",
    unsafe_allow_html=True,
)

# ---- Key Metrics ----
st.markdown('<div class="section-title">Key Metrics</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Overall Satisfaction", f"{ins_mean:.1f}")
with col2:
    st.metric("Market Average", f"{market_mean:.1f}")
with col3:
    g_col = gap_colour(gap)
    st.markdown(
        f'<div style="text-align:center;">'
        f'<p style="font-size:14px; color:{CI_DARK}; margin-bottom:4px;">Gap to Market</p>'
        f'<p style="font-size:26px; font-weight:bold; color:{g_col};">{gap:+.1f}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

# ---- Star Rating ----
st.markdown('<div class="section-title">Star Rating</div>', unsafe_allow_html=True)
if stars is not None:
    filled = "\u2605" * stars
    empty = "\u2606" * (5 - stars)
    st.markdown(
        f'<div style="text-align:center;">'
        f'<span style="font-size:48px; color:{CI_VIOLET};">{filled}{empty}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    ci_text = f"95% CI: {ci_lo:.1f} \u2013 {ci_hi:.1f}" if ci_lo and ci_hi else ""
    st.markdown(
        f'<p style="text-align:center; color:{CI_DARK}; font-size:13px;">'
        f"{ci_text} &nbsp;|&nbsp; "
        f"<span style='color:{t_col};'>{tier}</span> confidence</p>",
        unsafe_allow_html=True,
    )

# ---- Bar Chart — All Insurers ----
st.markdown(
    '<div class="section-title">Overall Satisfaction by Insurer</div>',
    unsafe_allow_html=True,
)

chart_df = eligible.sort_values("Q52_mean", ascending=True).copy()
colours = [CI_VIOLET if c == selected_insurer else CI_BLUE for c in chart_df["CurrentCompany"]]

chart_df["ci_lo"] = chart_df.apply(
    lambda r: confidence_interval(r["Q52_mean"], r["Q52_std"], int(r["Q52_n"]))[0]
    if pd.notna(r["Q52_std"]) else r["Q52_mean"],
    axis=1,
)
chart_df["ci_hi"] = chart_df.apply(
    lambda r: confidence_interval(r["Q52_mean"], r["Q52_std"], int(r["Q52_n"]))[1]
    if pd.notna(r["Q52_std"]) else r["Q52_mean"],
    axis=1,
)
chart_df["err_minus"] = chart_df["Q52_mean"] - chart_df["ci_lo"]
chart_df["err_plus"] = chart_df["ci_hi"] - chart_df["Q52_mean"]

fig = go.Figure()
fig.add_trace(go.Bar(
    y=chart_df["CurrentCompany"],
    x=chart_df["Q52_mean"],
    orientation="h",
    marker_color=colours,
    error_x=dict(
        type="data", symmetric=False,
        array=chart_df["err_plus"].tolist(),
        arrayminus=chart_df["err_minus"].tolist(),
        color=CI_DARK, thickness=1.5,
    ),
    text=[f"{v:.1f}" for v in chart_df["Q52_mean"]],
    textposition="outside",
    textfont=dict(family="Verdana", size=11, color=CI_DARK),
))
fig.add_vline(
    x=market_mean, line_dash="dash", line_color=CI_DARK,
    annotation_text=f"Market avg: {market_mean:.2f}",
    annotation_position="top",
    annotation_font=dict(family="Verdana", size=11, color=CI_DARK),
)
bar_height = max(400, len(chart_df) * 30)
fig.update_layout(
    height=bar_height,
    margin=dict(l=10, r=60, t=30, b=30),
    xaxis=dict(range=[1, 5.3], title=dict(text="Mean satisfaction (1-5)", font=dict(family="Verdana", size=12))),
    yaxis=dict(tickfont=dict(family="Verdana", size=11)),
    font=dict(family="Verdana"),
    plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
    showlegend=False,
)
st.plotly_chart(fig, width="stretch")

# ---- Q53 Diagnostic Statements ----
if not q53_df.empty and diagnostics_for_ai:
    st.markdown(
        '<div class="section-title">Claims Experience \u2014 Diagnostic Statements</div>',
        unsafe_allow_html=True,
    )
    rows_html = []
    for d in diagnostics_for_ai:
        g = d["gap"]
        g_c = gap_colour(g)
        rows_html.append(
            f"<tr>"
            f'<td style="padding:6px 10px;">{d["subject"]}</td>'
            f'<td style="padding:6px 10px; text-align:center;">{d["ins_mean"]:.1f}</td>'
            f'<td style="padding:6px 10px; text-align:center;">{d["mkt_mean"]:.1f}</td>'
            f'<td style="padding:6px 10px; text-align:center; color:{g_c}; font-weight:bold;">{g:+.1f}</td>'
            f"</tr>"
        )

    table_html = (
        f'<table style="width:100%; border-collapse:collapse; font-family:Verdana; font-size:13px;">'
        f"<thead><tr style='background:{CI_LGREY};'>"
        f'<th style="text-align:left; padding:8px 10px;">Statement</th>'
        f'<th style="text-align:center; padding:8px 10px;">{selected_insurer}</th>'
        f'<th style="text-align:center; padding:8px 10px;">Market</th>'
        f'<th style="text-align:center; padding:8px 10px;">Gap</th>'
        f"</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

# ---- Footer ----
st.markdown(
    f'<div style="text-align:center; font-size:11px; color:{CI_DARK}; '
    f'padding:16px 0; border-top:1px solid {CI_LGREY};">'
    "Data: IBT Motor survey &nbsp;|&nbsp; Minimum base: n=30 &nbsp;|&nbsp; "
    "95% confidence intervals shown &nbsp;|&nbsp; "
    "&copy; Consumer Intelligence 2026"
    "</div>",
    unsafe_allow_html=True,
)

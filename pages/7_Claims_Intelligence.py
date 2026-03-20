"""
Claims Intelligence — Motor & Home Insurance.
Satisfaction analysis from Q52/Q53 with AI-generated narrative,
star ratings with index positioning, CI bands, journey statements,
and sister brand notation.

Spec Sections 10.1–10.7.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.chart_export import apply_export_metadata, confidence_tooltip
from lib.config import (
    CI_BLUE, CI_DARK, CI_GREEN, CI_GREY, CI_LGREY, CI_LIGHT_GREY,
    CI_MAGENTA, CI_RED, CI_VIOLET, CI_WHITE,
    MIN_BASE_INDICATIVE, SISTER_BRANDS, Z_95,
    PRODUCTS,
)
from lib.narrative import generate_claims_narrative
from lib.state import format_month

FONT = "Verdana, Geneva, sans-serif"

# ---- Product selector ----
product = st.sidebar.selectbox("Product", PRODUCTS, key="claims_product")

st.markdown(
    f'<h1 style="color:{CI_VIOLET}; margin-top:0; font-family:{FONT};">'
    f"Claims Intelligence | {product} Insurance</h1>",
    unsafe_allow_html=True,
)

# ---- Get cached claims data ----
product_key = product.lower()
q52_key = f"claims_q52_{product_key}"
q53_key = f"claims_q53_{product_key}"

q52_df = st.session_state.get(q52_key, pd.DataFrame())
q53_df = st.session_state.get(q53_key, pd.DataFrame())

start_month = st.session_state.get("start_month")
end_month = st.session_state.get("end_month")

if q52_df.empty:
    st.warning(
        "No claims data cached. Go to **Admin / Governance** and click "
        "**Refresh from Power BI** to pull data."
    )
    st.stop()

# ---- Period label ----
if start_month and end_month:
    period_label = f"{format_month(start_month)} to {format_month(end_month)}"
else:
    period_label = "All cached data"

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

# ---- Insurer selector ----
insurer_list = sorted(eligible["CurrentCompany"].dropna().unique().tolist())
selected_insurer = st.sidebar.selectbox("Insurer (Claims)", insurer_list)

# ---- Insurer data ----
ins_row = q52_df[q52_df["CurrentCompany"] == selected_insurer]
if ins_row.empty:
    st.warning(f"No data for {selected_insurer} in the selected period.")
    st.stop()

ins_row = ins_row.iloc[0]
ins_n = int(ins_row["Q52_n"])
ins_mean = float(ins_row["Q52_mean"])
ins_std = float(ins_row["Q52_std"]) if pd.notna(ins_row["Q52_std"]) else 0.0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


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


def _get_rank_and_index(insurer_mean, all_means, market_mean):
    """Compute rank position and index score vs market."""
    sorted_desc = sorted(all_means, reverse=True)
    rank = sorted_desc.index(insurer_mean) + 1 if insurer_mean in sorted_desc else None
    index = (insurer_mean / market_mean * 100) if market_mean > 0 else None
    return rank, len(sorted_desc), index


def _sister_brand_note(insurer):
    """Return sister brand note if applicable."""
    sisters = SISTER_BRANDS.get(insurer)
    if sisters:
        return f"Note: {insurer} shares claims handling with {', '.join(sisters)}. Results may reflect shared operational processes."
    return None


# ---- Compute key metrics ----
ci_lo, ci_hi = confidence_interval(ins_mean, ins_std, ins_n)
ci_w = (ci_hi - ci_lo) if ci_lo is not None and ci_hi is not None else 999
tier = confidence_tier(ins_n, ci_w)
gap = ins_mean - market_mean
stars = assign_stars(ins_mean, all_eligible_means)
rank, total_insurers, index_score = _get_rank_and_index(ins_mean, all_eligible_means, market_mean)

if ins_n < MIN_BASE_INDICATIVE:
    st.error(f"Insufficient data for {selected_insurer}. Minimum 30 claimants required.")
    st.stop()

# ---- Active period banner ----
st.markdown(
    f'<div style="background:#F2F2F2; border-left:4px solid {CI_VIOLET}; '
    f'padding:10px 16px; margin-bottom:16px; font-family:{FONT}; font-size:14px; '
    f'color:#333;">'
    f'<b>Active period:</b> {period_label} &nbsp;|&nbsp; '
    f'<b>Product:</b> {product} &nbsp;|&nbsp; '
    f'<b>Insurer:</b> {selected_insurer} &nbsp;|&nbsp; '
    f'<b>Base:</b> n\u2009=\u2009{ins_n:,}'
    f'</div>',
    unsafe_allow_html=True,
)

# ---- Sister brand notation ----
sister_note = _sister_brand_note(selected_insurer)
if sister_note:
    st.markdown(
        f'<div style="background:white; border-left:4px solid {CI_BLUE}; '
        f'padding:10px 16px; margin-bottom:16px; font-family:{FONT}; font-size:13px; '
        f'color:{CI_GREY};">{sister_note}</div>',
        unsafe_allow_html=True,
    )

# ---- AI Narrative ----
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
    st.markdown(
        f'<div style="font-family:{FONT}; background:white; border:1px solid {CI_LIGHT_GREY}; '
        f'border-radius:4px; padding:20px 24px; margin-bottom:20px;">'
        f'<div style="font-size:16px; font-weight:bold; color:{CI_VIOLET}; margin-bottom:8px;">'
        f'{narrative["headline"]}</div>'
        f'<div style="font-size:13px; color:{CI_GREY}; font-style:italic; margin-bottom:12px;">'
        f'{narrative["subtitle"]}</div>'
        f'<div style="font-size:13px; color:{CI_GREY}; line-height:1.6;">'
        f'{narrative["paragraph"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ---- Confidence Banner ----
t_col = tier_colour(tier)
st.markdown(
    f'<div style="padding:12px; border-left:4px solid {t_col}; '
    f'background:{CI_LGREY}; margin-bottom:16px; font-family:{FONT}; font-size:13px;">'
    f"<strong>{selected_insurer}</strong> &mdash; "
    f"<strong style='color:{t_col}'>{tier}</strong> confidence &nbsp;|&nbsp; "
    f"<strong>{ins_n:,}</strong> claimant responses"
    f'<span style="float:right; cursor:help;" title="{confidence_tooltip("ci")}">\u2139\uFE0F</span>'
    f"</div>",
    unsafe_allow_html=True,
)

# ---- Key Metrics ----
st.markdown(
    f'<div style="font-family:{FONT}; font-size:15px; font-weight:bold; color:{CI_GREY}; '
    f'border-bottom:2px solid {CI_LIGHT_GREY}; padding-bottom:8px; margin-bottom:16px;">'
    f'Key Metrics</div>',
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Overall Satisfaction", f"{ins_mean:.2f}")
with col2:
    st.metric("Market Average", f"{market_mean:.2f}")
with col3:
    g_col = gap_colour(gap)
    st.markdown(
        f'<div style="text-align:center; font-family:{FONT};">'
        f'<p style="font-size:14px; color:{CI_DARK}; margin-bottom:4px;">Gap to Market</p>'
        f'<p style="font-size:26px; font-weight:bold; color:{g_col};">{gap:+.2f}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
with col4:
    idx_col = CI_GREEN if index_score and index_score > 100 else CI_RED if index_score and index_score < 100 else CI_GREY
    st.markdown(
        f'<div style="text-align:center; font-family:{FONT};">'
        f'<p style="font-size:14px; color:{CI_DARK}; margin-bottom:4px;">Index vs Market</p>'
        f'<p style="font-size:26px; font-weight:bold; color:{idx_col};">'
        f'{index_score:.0f}</p>'
        f"</div>" if index_score else "",
        unsafe_allow_html=True,
    )

# ---- Star Rating with Rank Positioning ----
st.markdown(
    f'<div style="font-family:{FONT}; font-size:15px; font-weight:bold; color:{CI_GREY}; '
    f'border-bottom:2px solid {CI_LIGHT_GREY}; padding-bottom:8px; margin:24px 0 16px 0;">'
    f'Star Rating</div>',
    unsafe_allow_html=True,
)

if stars is not None:
    filled = "\u2605" * stars
    empty = "\u2606" * (5 - stars)

    # Star description
    star_descriptions = {
        5: "Top quintile (top 20%)",
        4: "Second quintile (60th\u201380th percentile)",
        3: "Middle quintile (40th\u201360th percentile)",
        2: "Fourth quintile (20th\u201340th percentile)",
        1: "Bottom quintile (bottom 20%)",
    }

    rank_text = f"Ranked {rank} of {total_insurers}" if rank else ""
    ci_text = f"95% Confidence Interval: {ci_lo:.2f} \u2013 {ci_hi:.2f}" if ci_lo and ci_hi else ""

    st.markdown(
        f'<div style="text-align:center; font-family:{FONT};">'
        f'<span style="font-size:48px; color:{CI_VIOLET};">{filled}{empty}</span>'
        f'<div style="font-size:14px; color:{CI_GREY}; margin-top:6px;">'
        f'{star_descriptions.get(stars, "")}</div>'
        f'<div style="font-size:13px; color:{CI_GREY}; margin-top:4px;">'
        f'{rank_text} &nbsp;|&nbsp; {ci_text} &nbsp;|&nbsp; '
        f'<span style="color:{t_col};">{tier}</span> confidence</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Plain-English star rating tooltip
    st.markdown(
        f'<div style="background:{CI_LGREY}; padding:10px 16px; margin:12px 0; '
        f'font-family:{FONT}; font-size:12px; color:{CI_GREY}; border-radius:4px;">'
        f'{confidence_tooltip("stars")}</div>',
        unsafe_allow_html=True,
    )

# ---- Bar Chart — All Insurers with CI Bands ----
st.markdown(
    f'<div style="font-family:{FONT}; font-size:15px; font-weight:bold; color:{CI_GREY}; '
    f'border-bottom:2px solid {CI_LIGHT_GREY}; padding-bottom:8px; margin:24px 0 16px 0;">'
    f'Overall Satisfaction by Insurer</div>',
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
        color=CI_DARK, thickness=1.5, width=3,
    ),
    text=[f"{v:.2f}" for v in chart_df["Q52_mean"]],
    textposition="outside",
    textfont=dict(family=FONT, size=11, color=CI_DARK),
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Satisfaction: %{x:.2f}<br>"
        "95% Confidence Interval: [%{customdata[0]:.2f}, %{customdata[1]:.2f}]<br>"
        "n=%{customdata[2]:,}"
        "<extra></extra>"
    ),
    customdata=list(zip(
        chart_df["ci_lo"], chart_df["ci_hi"], chart_df["Q52_n"].astype(int),
    )),
))
fig.add_vline(
    x=market_mean, line_dash="dash", line_color=CI_DARK,
    annotation_text=f"Market avg: {market_mean:.2f}",
    annotation_position="top",
    annotation_font=dict(family=FONT, size=11, color=CI_DARK),
)
bar_height = max(400, len(chart_df) * 30)
fig.update_layout(
    height=bar_height,
    margin=dict(l=10, r=60, t=50, b=80),
    xaxis=dict(
        range=[1, 5.3],
        title=dict(text="Mean satisfaction (1-5)", font=dict(family=FONT, size=12)),
        gridcolor=CI_LIGHT_GREY,
    ),
    yaxis=dict(tickfont=dict(family=FONT, size=11), automargin=True),
    font=dict(family=FONT),
    plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
    showlegend=False,
)
apply_export_metadata(
    fig,
    title="Overall Claims Satisfaction by Insurer",
    period=period_label,
    base=int(total_n),
    question="Q52",
    subtitle="Mean satisfaction score (1-5) with 95% confidence intervals",
)
st.plotly_chart(fig, use_container_width=True)

# ---- Q53 Journey Statement Detail ----
if not q53_df.empty and diagnostics_for_ai:
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:15px; font-weight:bold; color:{CI_GREY}; '
        f'border-bottom:2px solid {CI_LIGHT_GREY}; padding-bottom:8px; margin:24px 0 16px 0;">'
        f'Claims Journey — Diagnostic Statements (Q53)</div>',
        unsafe_allow_html=True,
    )

    # Sort diagnostics by gap (worst first for easy identification)
    sorted_diag = sorted(diagnostics_for_ai, key=lambda d: d["gap"])

    rows_html = []
    for d in sorted_diag:
        g = d["gap"]
        g_c = gap_colour(g)
        # Visual indicator
        if g > 0.1:
            indicator = f'<span style="color:{CI_GREEN};">\u25B2</span>'
        elif g < -0.1:
            indicator = f'<span style="color:{CI_RED};">\u25BC</span>'
        else:
            indicator = f'<span style="color:{CI_GREY};">\u25C6</span>'

        rows_html.append(
            f"<tr>"
            f'<td style="padding:8px 12px; border-bottom:1px solid {CI_LIGHT_GREY};">{d["subject"]}</td>'
            f'<td style="padding:8px 12px; text-align:center; border-bottom:1px solid {CI_LIGHT_GREY}; '
            f'font-weight:bold; color:{CI_VIOLET};">{d["ins_mean"]:.2f}</td>'
            f'<td style="padding:8px 12px; text-align:center; border-bottom:1px solid {CI_LIGHT_GREY}; '
            f'color:{CI_GREY};">{d["mkt_mean"]:.2f}</td>'
            f'<td style="padding:8px 12px; text-align:center; border-bottom:1px solid {CI_LIGHT_GREY}; '
            f'color:{g_c}; font-weight:bold;">{indicator} {g:+.2f}</td>'
            f"</tr>"
        )

    header_style = (
        f"background:{CI_LGREY}; font-weight:bold; padding:10px 12px; "
        f"border-bottom:2px solid {CI_GREY}; font-size:12px; text-transform:uppercase; "
        f"letter-spacing:0.5px; color:{CI_GREY};"
    )

    table_html = (
        f'<table style="width:100%; border-collapse:collapse; font-family:{FONT}; font-size:13px;">'
        f"<thead><tr>"
        f'<th style="{header_style} text-align:left;">Statement</th>'
        f'<th style="{header_style} text-align:center;">{selected_insurer}</th>'
        f'<th style="{header_style} text-align:center;">Market</th>'
        f'<th style="{header_style} text-align:center;">Gap</th>'
        f"</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    st.caption(
        f"Statements sorted by gap (lowest first). "
        f"Source: Q53 | Period: {period_label} | Minimum n={MIN_BASE_INDICATIVE} per statement."
    )

# ---- Footer ----
st.markdown(
    f'<div style="text-align:center; font-size:11px; color:{CI_DARK}; font-family:{FONT}; '
    f'padding:16px 0; border-top:1px solid {CI_LGREY};">'
    f"Data: IBT {product} survey &nbsp;|&nbsp; Period: {period_label} &nbsp;|&nbsp; "
    f"Minimum base: n={MIN_BASE_INDICATIVE} &nbsp;|&nbsp; "
    f"95% confidence intervals shown &nbsp;|&nbsp; "
    f"&copy; Consumer Intelligence 2026"
    f"</div>",
    unsafe_allow_html=True,
)

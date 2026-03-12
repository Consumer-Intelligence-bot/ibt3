"""
Insurer Comparison — Side-by-side view of key metrics across all insurers
meeting minimum base threshold (Spec Section 7).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.confidence import MetricType, assess_confidence, calc_ci_width
from lib.analytics.demographics import apply_filters
from lib.analytics.flows import calc_net_flow
from lib.analytics.rates import calc_shopping_rate, calc_retention_rate
from lib.analytics.trends import calc_trend
from lib.chart_export import apply_export_metadata, heading_with_tooltip
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    MIN_BASE_PUBLISHABLE,
)
from lib.state import format_year_month, render_global_filters, get_ss_data

st.header("Insurer Comparison")

FONT = "Verdana, Geneva, sans-serif"

# ---- Filters (no insurer selector needed — this page shows ALL insurers) ----
filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

df_mkt = apply_filters(
    df_motor,
    insurer=None,
    age_band=filters["age_band"],
    region=filters["region"],
    payment_type=filters["payment_type"],
    product=product,
    selected_months=selected_months,
)

if len(df_mkt) == 0:
    st.warning("No data for the selected filters.")
    st.stop()

# ---- Active period label ----
if selected_months:
    period_label = f"{format_year_month(min(selected_months))} – {format_year_month(max(selected_months))}"
else:
    months_in_data = sorted(df_mkt["RenewalYearMonth"].dropna().unique())
    if len(months_in_data) > 0:
        period_label = f"{format_year_month(months_in_data[0])} – {format_year_month(months_in_data[-1])}"
    else:
        period_label = ""

st.caption(f"Active period: **{period_label}**")


# ---------------------------------------------------------------------------
# Build per-insurer metrics
# ---------------------------------------------------------------------------
def _pct(n, d):
    return n / d if d > 0 else 0.0


# Market-level retention (prior for Bayesian smoothing)
mkt_existing = df_mkt[~df_mkt["IsNewToMarket"]]
mkt_retained = mkt_existing[~mkt_existing["IsSwitcher"]]
mkt_retention_rate = _pct(len(mkt_retained), len(mkt_existing)) if len(mkt_existing) > 0 else 0.5

# Discover all insurers from PreviousCompany (renewals base)
all_insurers = (
    df_mkt["PreviousCompany"]
    .dropna()
    .loc[lambda s: s != ""]
    .unique()
    .tolist()
)

rows = []
for ins in sorted(all_insurers):
    # Renewal base: existing customers of this insurer
    ins_existing = mkt_existing[mkt_existing["PreviousCompany"] == ins]
    n_renewals = len(ins_existing)

    if n_renewals < MIN_BASE_PUBLISHABLE:
        continue

    ins_retained = ins_existing[~ins_existing["IsSwitcher"]]
    successes = len(ins_retained)

    # Bayesian-smoothed retention
    bay = bayesian_smooth_rate(successes, n_renewals, mkt_retention_rate)

    # Shopping rate for this insurer's renewals
    shopping_rate = calc_shopping_rate(ins_existing)

    # Net flow
    nf = calc_net_flow(df_mkt, ins)

    # Trend (uses calc_trend with market_rate)
    trend = calc_trend(ins_existing, mkt_retention_rate)

    # Confidence assessment
    ci_width_pp = (bay["ci_upper"] - bay["ci_lower"]) * 100
    conf = assess_confidence(
        n_renewals,
        bay["posterior_mean"],
        MetricType.RATE,
        posterior_ci_width=ci_width_pp,
    )

    rows.append(
        {
            "insurer": ins,
            "n_renewals": n_renewals,
            "retention": bay["posterior_mean"],
            "ci_lower": bay["ci_lower"],
            "ci_upper": bay["ci_upper"],
            "raw_retention": bay["raw_rate"],
            "shopping_rate": shopping_rate,
            "net_flow": nf["net"],
            "gained": nf["gained"],
            "lost": nf["lost"],
            "trend_direction": trend["direction"],
            "trend_change": trend["change"],
            "trend_suppressed": trend["suppressed"],
            "confidence_label": conf.label.value,
            "confidence_can_show": conf.can_show,
            "ci_width_pp": ci_width_pp,
        }
    )

if not rows:
    st.info(
        f"No insurers meet the minimum base of {MIN_BASE_PUBLISHABLE} renewals "
        f"in the selected period. Try widening the time window."
    )
    st.stop()

df_comp = pd.DataFrame(rows).sort_values("retention", ascending=False).reset_index(drop=True)


# ===========================================================================
# Section 1: Retention Comparison Chart (Spec 7.2)
# ===========================================================================
st.markdown(heading_with_tooltip("Retention Comparison", "Q15", level="subheader"), unsafe_allow_html=True)

fig = go.Figure()

# Sort ascending for horizontal bar (top of chart = highest)
df_chart = df_comp.sort_values("retention", ascending=True).reset_index(drop=True)

bar_colours = [
    CI_GREEN if r["retention"] >= mkt_retention_rate else CI_RED
    for _, r in df_chart.iterrows()
]

error_lower = [(r["retention"] - r["ci_lower"]) for _, r in df_chart.iterrows()]
error_upper = [(r["ci_upper"] - r["retention"]) for _, r in df_chart.iterrows()]

fig.add_trace(
    go.Bar(
        y=df_chart["insurer"],
        x=df_chart["retention"],
        orientation="h",
        marker_color=bar_colours,
        error_x=dict(
            type="data",
            symmetric=False,
            array=error_upper,
            arrayminus=error_lower,
            color=CI_GREY,
            thickness=1.5,
            width=3,
        ),
        text=[f"{v * 100:.1f}%" for v in df_chart["retention"]],
        textposition="outside",
        textfont=dict(family=FONT, size=11),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Retention: %{x:.1%}<br>"
            "95% CI: [%{customdata[0]:.1%}, %{customdata[1]:.1%}]<br>"
            "n=%{customdata[2]:,}"
            "<extra></extra>"
        ),
        customdata=list(
            zip(
                df_chart["ci_lower"],
                df_chart["ci_upper"],
                df_chart["n_renewals"],
            )
        ),
    )
)

# Market average reference line
fig.add_vline(
    x=mkt_retention_rate,
    line_dash="dash",
    line_color=CI_GREY,
    line_width=1.5,
    annotation_text=f"Market avg: {mkt_retention_rate * 100:.1f}%",
    annotation_position="top",
    annotation_font=dict(family=FONT, size=10, color=CI_GREY),
)

chart_height = max(350, len(df_chart) * 32 + 80)

fig.update_layout(
    height=chart_height,
    margin=dict(l=10, r=80, t=50, b=60),
    xaxis=dict(
        tickformat=".0%",
        title="Bayesian-smoothed retention rate",
        title_font=dict(family=FONT, size=11, color=CI_GREY),
        gridcolor=CI_LIGHT_GREY,
        zeroline=False,
    ),
    yaxis=dict(
        automargin=True,
        tickfont=dict(family=FONT, size=11),
    ),
    showlegend=False,
    font=dict(family=FONT),
    plot_bgcolor="white",
    paper_bgcolor="white",
)

fig = apply_export_metadata(
    fig,
    title="Retention Comparison by Insurer",
    subtitle="Bayesian-smoothed retention with 95% credible intervals",
    period=period_label,
    base=len(mkt_existing),
    question="Q15",
)

st.plotly_chart(fig, use_container_width=True)


# ===========================================================================
# Section 2: Metrics Table (Spec 7.3)
# ===========================================================================
st.markdown("### Metrics Table")


def _fmt_pct(val, dp=1):
    if val is None:
        return "\u2014"
    return f"{val * 100:.{dp}f}%"


def _trend_arrow(direction, suppressed):
    if suppressed or direction is None:
        return "\u2014"
    if direction == "up":
        return "\u2191"  # up arrow
    if direction == "down":
        return "\u2193"  # down arrow
    return "\u2194"  # left-right arrow for stable


def _confidence_icon(label):
    if label == "HIGH":
        return "\u2713"  # checkmark
    if label == "MEDIUM":
        return "\u25CB"  # open circle
    if label == "LOW":
        return "\u26A0"  # warning
    return "\u2716"  # cross


def _colour_vs_market(val, market_val):
    """Return inline CSS colour comparing value to market."""
    if val is None or market_val is None:
        return ""
    if val > market_val:
        return f"color: {CI_GREEN}; font-weight: bold;"
    if val < market_val:
        return f"color: {CI_RED}; font-weight: bold;"
    return ""


def _net_flow_colour(net):
    if net > 0:
        return f"color: {CI_GREEN}; font-weight: bold;"
    if net < 0:
        return f"color: {CI_RED}; font-weight: bold;"
    return ""


def _net_flow_label(net):
    if net > 0:
        return f"+{net:,}"
    return f"{net:,}"


# Build styled HTML table for richer formatting than st.dataframe
table_rows = []
for _, r in df_comp.iterrows():
    is_low = r["confidence_label"] in ("LOW", "INSUFFICIENT")
    row_style = "font-style: italic; opacity: 0.75;" if is_low else ""

    retention_style = _colour_vs_market(r["retention"], mkt_retention_rate)
    net_style = _net_flow_colour(r["net_flow"])
    trend = _trend_arrow(r["trend_direction"], r["trend_suppressed"])
    conf = _confidence_icon(r["confidence_label"])

    # Trend colour
    trend_colour = CI_GREY
    if r["trend_direction"] == "up":
        trend_colour = CI_GREEN
    elif r["trend_direction"] == "down":
        trend_colour = CI_RED

    warning_suffix = ' <span title="Low confidence — interpret with caution">\u26A0</span>' if is_low else ""

    table_rows.append(
        f"<tr style='{row_style}'>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY};'>"
        f"{r['insurer']}{warning_suffix}</td>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY}; text-align: right;'>"
        f"{r['n_renewals']:,}</td>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY}; text-align: right; {retention_style}'>"
        f"{_fmt_pct(r['retention'])}</td>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY}; text-align: right;'>"
        f"{_fmt_pct(r['shopping_rate'])}</td>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY}; text-align: right; {net_style}'>"
        f"{_net_flow_label(r['net_flow'])}</td>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY}; text-align: center; "
        f"color: {trend_colour}; font-size: 18px;'>{trend}</td>"
        f"<td style='padding: 8px 12px; border-bottom: 1px solid {CI_LIGHT_GREY}; text-align: center;'>"
        f"{conf}</td>"
        f"</tr>"
    )

header_style = (
    f"background: {CI_LIGHT_GREY}; font-weight: bold; padding: 10px 12px; "
    f"border-bottom: 2px solid {CI_GREY}; font-size: 12px; text-transform: uppercase; "
    f"letter-spacing: 0.5px; color: {CI_GREY};"
)

html_table = f"""
<div style="overflow-x: auto;">
<table style="width: 100%; border-collapse: collapse; font-family: {FONT}; font-size: 13px;">
<thead>
<tr>
    <th style="{header_style} text-align: left;">Insurer</th>
    <th style="{header_style} text-align: right;">Renewals</th>
    <th style="{header_style} text-align: right;">Retention</th>
    <th style="{header_style} text-align: right;">Shopping Rate</th>
    <th style="{header_style} text-align: right;">Net Flow</th>
    <th style="{header_style} text-align: center;">Trend</th>
    <th style="{header_style} text-align: center;">Confidence</th>
</tr>
</thead>
<tbody>
{"".join(table_rows)}
</tbody>
</table>
</div>
"""

st.markdown(html_table, unsafe_allow_html=True)

# Legend
st.markdown(
    f"""
<div style="font-family: {FONT}; font-size: 11px; color: {CI_GREY}; margin-top: 12px; line-height: 1.8;">
    <b>Legend:</b>&ensp;
    <span style="color: {CI_GREEN};">\u25CF</span> Above market&emsp;
    <span style="color: {CI_RED};">\u25CF</span> Below market&emsp;
    \u2191 Improving&emsp;
    \u2193 Declining&emsp;
    \u2194 Stable&emsp;
    \u2713 High confidence&emsp;
    \u25CB Medium&emsp;
    \u26A0 Low confidence
</div>
""",
    unsafe_allow_html=True,
)


# ---- Interactive sort (alternative dataframe view) ----
with st.expander("Sortable data view"):
    df_display = df_comp[
        ["insurer", "n_renewals", "retention", "shopping_rate", "net_flow", "trend_direction", "confidence_label"]
    ].copy()
    df_display.columns = ["Insurer", "Renewals", "Retention", "Shopping Rate", "Net Flow", "Trend", "Confidence"]
    df_display["Retention"] = df_display["Retention"].apply(lambda v: f"{v * 100:.1f}%")
    df_display["Shopping Rate"] = df_display["Shopping Rate"].apply(
        lambda v: f"{v * 100:.1f}%" if v is not None else "\u2014"
    )
    df_display["Net Flow"] = df_display["Net Flow"].apply(_net_flow_label)
    df_display["Trend"] = df_display["Trend"].apply(lambda v: v if v else "\u2014")
    st.dataframe(df_display, use_container_width=True, hide_index=True)


# ---- Footer ----
st.caption(
    f"Base: {len(mkt_existing):,} existing customers | "
    f"Minimum {MIN_BASE_PUBLISHABLE} renewals per insurer | "
    f"Market retention: {mkt_retention_rate * 100:.1f}%"
)

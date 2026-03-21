"""
Flow Intelligence — Over/under-index analysis for customer losses and gains
relative to the market average. Expressed as a 100-based index.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.flows import calc_flow_index
from lib.analytics.suppression import check_suppression
from lib.config import (
    CI_BLUE,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT, render_header
from lib.state import (
    format_year_month,
    get_filtered_data,
    get_ss_data,
    render_global_filters,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

render_header()
st.header("Flow Intelligence")

_section_divider = section_divider
_period_label = period_label


# ---------------------------------------------------------------------------
# Filters & data loading
# ---------------------------------------------------------------------------

filters = render_global_filters()
df_ins, df_mkt = get_filtered_data(
    insurer=filters["insurer"],
    product=filters["product"],
    age_band=filters["age_band"],
    region=filters["region"],
    payment_type=filters["payment_type"],
    selected_months=filters["selected_months"],
)

if not filters["insurer"]:
    st.info("Select an insurer from the sidebar to view Flow Intelligence.")
    st.stop()

insurer = filters["insurer"]

# Suppression gate
n_ins = len(df_ins)
if n_ins < MIN_BASE_PUBLISHABLE:
    st.warning(
        f"Insufficient data: {n_ins:,} respondents "
        f"(minimum {MIN_BASE_PUBLISHABLE} required). Try broadening your selection."
    )
    st.stop()

# Compute flow index once
result = calc_flow_index(df_mkt, insurer)

# ---------------------------------------------------------------------------
# Section 1: Loss over-index
# ---------------------------------------------------------------------------

_section_divider("Where Are We Losing Disproportionately?")

df_loss = result["loss_index"]

if df_loss.empty:
    st.info("Insufficient data to calculate loss over-index for the selected period.")
else:
    n = len(df_loss)
    colours = [
        CI_RED if row["index"] > 120
        else CI_GREEN if row["index"] < 80
        else CI_BLUE
        for _, row in df_loss.iterrows()
    ]

    fig = go.Figure(go.Bar(
        x=df_loss["index"],
        y=df_loss["competitor"],
        orientation="h",
        marker_color=colours,
        text=[f"{v:.0f}" for v in df_loss["index"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Index: %{x:.0f}<br>"
            "Your share: %{customdata[0]:.1%}<br>"
            "Market share: %{customdata[1]:.1%}<br>"
            "Raw count: %{customdata[2]:,}"
            "<extra></extra>"
        ),
        customdata=df_loss[["insurer_share", "market_share", "raw_count"]].values,
    ))

    fig.add_vline(
        x=100,
        line_dash="dot",
        line_color=CI_MAGENTA,
        annotation_text="Market average (100)",
        annotation_position="top right",
        annotation_font_color=CI_MAGENTA,
    )

    fig.update_layout(
        height=max(400, n * 30),
        xaxis=dict(
            title="Index (100 = market average)",
            gridcolor=CI_LIGHT_GREY,
        ),
        yaxis=dict(title="", autorange="reversed"),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        font=dict(family="Verdana, Geneva, sans-serif", size=11, color=CI_GREY),
        margin=dict(l=10, r=80, t=20, b=40),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Index above 100 means you are losing a disproportionately high share "
        "of customers to that competitor vs the market average. "
        f"Based on {result['insurer_lost']:,} customers lost in the selected period."
    )

# ---------------------------------------------------------------------------
# Section 2: Gain over-index
# ---------------------------------------------------------------------------

_section_divider("Where Are We Winning Disproportionately?")

df_gain = result["gain_index"]

if df_gain.empty:
    st.info("Insufficient data to calculate gain over-index for the selected period.")
else:
    n = len(df_gain)
    colours = [
        CI_GREEN if row["index"] > 120
        else CI_RED if row["index"] < 80
        else CI_BLUE
        for _, row in df_gain.iterrows()
    ]

    fig = go.Figure(go.Bar(
        x=df_gain["index"],
        y=df_gain["competitor"],
        orientation="h",
        marker_color=colours,
        text=[f"{v:.0f}" for v in df_gain["index"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Index: %{x:.0f}<br>"
            "Your share: %{customdata[0]:.1%}<br>"
            "Market share: %{customdata[1]:.1%}<br>"
            "Raw count: %{customdata[2]:,}"
            "<extra></extra>"
        ),
        customdata=df_gain[["insurer_share", "market_share", "raw_count"]].values,
    ))

    fig.add_vline(
        x=100,
        line_dash="dot",
        line_color=CI_MAGENTA,
        annotation_text="Market average (100)",
        annotation_position="top right",
        annotation_font_color=CI_MAGENTA,
    )

    fig.update_layout(
        height=max(400, n * 30),
        xaxis=dict(
            title="Index (100 = market average)",
            gridcolor=CI_LIGHT_GREY,
        ),
        yaxis=dict(title="", autorange="reversed"),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        font=dict(family="Verdana, Geneva, sans-serif", size=11, color=CI_GREY),
        margin=dict(l=10, r=80, t=20, b=40),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Index above 100 means you are winning a disproportionately high share "
        "of customers from that competitor vs the market average. "
        f"Based on {result['insurer_gained']:,} customers gained in the selected period."
    )

# ---------------------------------------------------------------------------
# Section 3: Trend drill-down
# ---------------------------------------------------------------------------

_section_divider("How Is This Changing Over Time?")

col1, col2 = st.columns(2)
with col1:
    direction = st.selectbox(
        "Flow direction",
        ["Losses (outflow)", "Gains (inflow)"],
        key="flow_direction",
    )
with col2:
    if direction == "Losses (outflow)":
        competitors = result["loss_index"]["competitor"].tolist()
    else:
        competitors = result["gain_index"]["competitor"].tolist()

    if not competitors:
        st.info("No eligible competitors to drill into.")
        st.stop()

    selected_competitor = st.selectbox(
        "Competitor",
        competitors,
        key="flow_competitor",
    )

# Compute month-by-month index from full dataset
df_all, _ = get_ss_data()

if df_all.empty or "RenewalYearMonth" not in df_all.columns:
    st.info("Insufficient monthly data to show a meaningful trend for this pair.")
    st.stop()

# Filter by product
product = filters["product"]
if "Product" in df_all.columns:
    df_all = df_all[df_all["Product"] == product]

# Get months in the selected time window
if filters["selected_months"]:
    months = sorted(filters["selected_months"])
else:
    months = sorted(df_all["RenewalYearMonth"].dropna().unique().astype(int).tolist())

exclude_pattern = r"Don't Know|Can't Remember|Other"

trend_rows = []
for month in months:
    df_month = df_all[df_all["RenewalYearMonth"] == month]
    if df_month.empty:
        continue

    # Apply same filtering as calc_flow_index
    from lib.analytics.flows import _exclude_q4_eq_q39
    sw = _exclude_q4_eq_q39(df_month)
    sw = sw[sw["IsSwitcher"]].copy()
    sw = sw[
        sw["PreviousCompany"].notna() & (sw["PreviousCompany"] != "")
        & sw["CurrentCompany"].notna() & (sw["CurrentCompany"] != "")
    ]
    sw = sw[
        ~sw["PreviousCompany"].str.contains(exclude_pattern, case=False, na=False)
        & ~sw["CurrentCompany"].str.contains(exclude_pattern, case=False, na=False)
    ]

    total_sw = len(sw)
    if total_sw == 0:
        continue

    if direction == "Losses (outflow)":
        # insurer losing to selected_competitor
        pair_count = len(sw[(sw["PreviousCompany"] == insurer) & (sw["CurrentCompany"] == selected_competitor)])
        insurer_total = len(sw[sw["PreviousCompany"] == insurer])
        market_dest = len(sw[sw["CurrentCompany"] == selected_competitor])

        if insurer_total == 0 or market_dest == 0:
            continue
        insurer_share = pair_count / insurer_total
        market_share = market_dest / total_sw
    else:
        # insurer gaining from selected_competitor
        pair_count = len(sw[(sw["PreviousCompany"] == selected_competitor) & (sw["CurrentCompany"] == insurer)])
        insurer_total = len(sw[sw["CurrentCompany"] == insurer])
        market_source = len(sw[sw["PreviousCompany"] == selected_competitor])

        if insurer_total == 0 or market_source == 0:
            continue
        insurer_share = pair_count / insurer_total
        market_share = market_source / total_sw

    if market_share == 0:
        continue

    # Suppress months with low counts
    if pair_count < MIN_BASE_FLOW_CELL:
        trend_rows.append({
            "month": month,
            "month_label": format_year_month(month),
            "index": None,  # gap in line
            "raw_count": pair_count,
        })
    else:
        trend_rows.append({
            "month": month,
            "month_label": format_year_month(month),
            "index": (insurer_share / market_share) * 100,
            "raw_count": pair_count,
        })

trend_df = pd.DataFrame(trend_rows)

if trend_df.empty or trend_df["index"].notna().sum() < 3:
    st.info("Insufficient monthly data to show a meaningful trend for this pair.")
    st.stop()

fig = go.Figure(go.Scatter(
    x=trend_df["month_label"],
    y=trend_df["index"],
    mode="lines+markers",
    line=dict(color=CI_MAGENTA, width=2),
    marker=dict(size=6, color=CI_MAGENTA),
    hovertemplate="<b>%{x}</b><br>Index: %{y:.0f}<extra></extra>",
    connectgaps=False,
))

fig.add_hline(
    y=100,
    line_dash="dot",
    line_color=CI_GREY,
    annotation_text="Market average (100)",
    annotation_position="right",
)

fig.update_layout(
    height=320,
    xaxis=dict(title="", gridcolor=CI_LIGHT_GREY),
    yaxis=dict(title="Index", gridcolor=CI_LIGHT_GREY),
    plot_bgcolor=CI_WHITE,
    paper_bgcolor=CI_WHITE,
    font=dict(family="Verdana, Geneva, sans-serif", size=11, color=CI_GREY),
    margin=dict(l=10, r=80, t=20, b=40),
    showlegend=False,
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
period = _period_label(filters["selected_months"])
st.caption(
    f"Flow Intelligence | {insurer} | {filters['product']} | {period} | "
    f"Insurer base: {n_ins:,} | Total switchers: {result['total_switchers']:,}"
)

"""
Brand Awareness — Market View.

Implements Changes 1–5 from the Brand Awareness Dashboard spec:
  1. Dual period selector (Period A / Period B comparison)
  2. Rank-enriched "Most Improved" callout
  3. Movement-threshold filter
  4. Separate Absolute and Mover views
  5. Suppression rules for thin periods
  6. Multi-brand trend line chart (Spec Section 9.6)
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.awareness import (
    Q1_GATING_MESSAGE,
    apply_movement_filters,
    calc_awareness_movers,
    calc_awareness_rates,
    calc_dual_period_comparison,
    calc_most_improved_enriched,
)
from lib.analytics.demographics import apply_filters
from lib.chart_export import apply_export_metadata
from lib.config import (
    BUMP_COLOURS,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_RED,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
)
from lib.state import (
    format_year_month,
    render_dual_period_selector,
    render_global_filters,
    get_ss_data,
)

st.header("Brand Awareness — Market View")

# ---- Global filters ----
filters = render_global_filters()
df_motor, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

# ---- Awareness level toggle ----
level = st.radio(
    "Awareness level",
    ["prompted", "consideration"],
    format_func=lambda x: {
        "prompted": "Prompted (Q2)",
        "consideration": "Consideration (Q27)",
    }.get(x, x),
    horizontal=True,
)

# ---- Change 1: Dual period selector ----
periods = render_dual_period_selector()
if periods is None:
    st.warning("Insufficient data to build period comparison. Need at least two distinct survey months.")
    st.stop()

period_a_months = periods["period_a_months"]
period_b_months = periods["period_b_months"]
caption = periods["caption"]

# Apply product filter to main data
df_main = apply_filters(df_motor, product=product)

# Low-data warning (n < 50 at market level)
n_a = df_main[df_main["RenewalYearMonth"].isin(period_a_months)]["UniqueID"].nunique()
n_b = df_main[df_main["RenewalYearMonth"].isin(period_b_months)]["UniqueID"].nunique()
if n_a < MIN_BASE_PUBLISHABLE or n_b < MIN_BASE_PUBLISHABLE:
    st.warning(
        "One or both periods have limited data. "
        "Market-level metrics shown; insurer-level metrics may be suppressed."
    )

# ---- Compute dual-period comparison ----
with st.spinner("Calculating awareness comparison..."):
    comparison = calc_dual_period_comparison(
        df_main, level,
        period_a_months, period_b_months,
    )
if comparison.empty:
    st.warning("No awareness data available for this selection.")
    st.stop()

# Filter out "Other" when toggle is off
if not filters.get("include_other", False):
    comparison = comparison[comparison["brand"].str.lower() != "other"]
    if comparison.empty:
        st.warning("No awareness data available after excluding 'Other'.")
        st.stop()

# Period caption on every section
st.caption(caption)

# ---- Change 2: Rank-enriched "Most Improved" callout ----
st.subheader("Summary")

most_improved = calc_most_improved_enriched(comparison)

col1, col2, col3, col4 = st.columns(4)

# Brands eligible (in Period B)
eligible_brands = comparison[comparison["combined_tier"].isin(["full", "indicative"])]
with col1:
    st.metric("Brands Eligible", f"{len(eligible_brands):,}")

# Market average (Period B)
with col2:
    avg_b = eligible_brands["rate_b"].mean() if not eligible_brands.empty else 0
    st.metric("Market Average", f"{avg_b:.1%}")

# Highest awareness (Period B)
with col3:
    if not eligible_brands.empty:
        top_row = eligible_brands.loc[eligible_brands["rate_b"].idxmax()]
        st.metric("Highest Awareness", f"{top_row['rate_b']:.1%}")
        st.caption(top_row["brand"])
    else:
        st.metric("Highest Awareness", "—")

# Most improved — enriched callout
with col4:
    if most_improved:
        mi = most_improved
        st.metric("Most Improved", mi["brand"])
        st.markdown(
            f"Awareness: **{mi['rate_b']:.0%}** (was {mi['rate_a']:.0%}) &nbsp;|&nbsp; "
            f"Change: **{mi['rate_change_pp']:+.0f}pp**  \n"
            f"Rank: **{mi['rank_b']}** (was {mi['rank_a']}) &nbsp;|&nbsp; "
            f"**{mi['direction_text']}**",
            unsafe_allow_html=True,
        )
    else:
        st.metric("Most Improved", "—")
        st.caption("Insufficient data to identify most improved brand in the selected period.")

# ---- Change 3: Movement-threshold filter ----
st.sidebar.markdown("---")
st.sidebar.subheader("Awareness Filters")

show_all = st.sidebar.checkbox("Show all brands", value=False)

min_rank_move = None
min_pp_change = None
top_n = None
pinned_brands = []

if not show_all:
    use_rank_move = st.sidebar.checkbox("Minimum rank movement", value=True)
    if use_rank_move:
        min_rank_move = st.sidebar.number_input(
            "Min rank positions moved", min_value=1, max_value=50, value=5, step=1,
        )

    use_pp_change = st.sidebar.checkbox("Minimum awareness change (pp)", value=False)
    if use_pp_change:
        min_pp_change = st.sidebar.number_input(
            "Min awareness change (pp)", min_value=0.5, max_value=50.0, value=3.0, step=0.5,
        )

    use_top_n = st.sidebar.checkbox("Top N by current awareness", value=False)
    if use_top_n:
        top_n = st.sidebar.slider("Top N brands", min_value=5, max_value=30, value=15)

# Brand search (pin)
all_brands = sorted(comparison["brand"].unique().tolist())
pinned_brands = st.sidebar.multiselect("Pin specific brands", options=all_brands)

# Apply filters
if show_all:
    filtered = comparison.copy()
else:
    filtered = apply_movement_filters(
        comparison,
        min_rank_movement=min_rank_move,
        min_awareness_change_pp=min_pp_change,
        top_n=top_n,
        pinned_brands=pinned_brands,
    )

# Build dynamic chart title
if show_all:
    filter_title = "All brands"
elif min_rank_move and not min_pp_change and not top_n:
    filter_title = f"Brands moving {min_rank_move} or more rank positions"
elif min_pp_change and not min_rank_move and not top_n:
    filter_title = f"Brands with {min_pp_change:.0f}pp+ awareness change"
elif top_n and not min_rank_move and not min_pp_change:
    filter_title = f"Top {top_n} brands by current awareness"
else:
    parts = []
    if min_rank_move:
        parts.append(f"≥{min_rank_move} rank positions")
    if min_pp_change:
        parts.append(f"≥{min_pp_change:.0f}pp change")
    if top_n:
        parts.append(f"top {top_n}")
    filter_title = "Brands: " + ", ".join(parts) if parts else "Filtered brands"

# ---- Change 4: Separate Absolute and Mover views ----
view = st.radio(
    "View",
    ["Awareness level", "Awareness movement"],
    horizontal=True,
    help="Level view: ranked by current awareness. Movement view: ranked by rank change.",
)

st.caption(caption)

if view == "Awareness level":
    # ---- Awareness Level View ----
    st.subheader(f"Awareness Level — {filter_title}")

    chart_data = filtered.sort_values("rate_b", ascending=True)

    # Change 5: visual indicator for thin data
    bar_colours = []
    patterns = []
    for _, row in chart_data.iterrows():
        if row["combined_tier"] == "suppress":
            bar_colours.append(CI_LIGHT_GREY)
            patterns.append("/")
        elif row["combined_tier"] == "indicative":
            bar_colours.append(CI_GREY)
            patterns.append("")
        else:
            bar_colours.append(CI_GREEN)
            patterns.append("")

    market_avg = chart_data.loc[
        chart_data["combined_tier"].isin(["full", "indicative"]), "rate_b"
    ].mean()

    fig = go.Figure()

    # Period A bars (lighter, behind)
    fig.add_trace(go.Bar(
        y=chart_data["brand"],
        x=chart_data["rate_a"],
        orientation="h",
        name=periods["period_a_label"],
        marker_color=CI_LIGHT_GREY,
        text=[f"{r:.0%}" for r in chart_data["rate_a"]],
        textposition="inside",
        textfont=dict(size=10, color=CI_GREY),
    ))

    # Period B bars (foreground)
    fig.add_trace(go.Bar(
        y=chart_data["brand"],
        x=chart_data["rate_b"],
        orientation="h",
        name=periods["period_b_label"],
        marker_color=bar_colours,
        text=[
            f"{r:.0%}  (Rank {rk})"
            for r, rk in zip(chart_data["rate_b"], chart_data["rank_b"])
        ],
        textposition="outside",
        textfont=dict(size=10),
    ))

    # Market average reference line
    if market_avg and market_avg > 0:
        fig.add_vline(
            x=market_avg, line_dash="dash", line_color=MARKET_COLOUR, line_width=1.5,
            annotation_text=f"Market avg: {market_avg:.0%}",
            annotation_font_size=11, annotation_font_color=MARKET_COLOUR,
        )

    fig.update_layout(
        barmode="overlay",
        xaxis_tickformat=".0%",
        height=max(400, len(chart_data) * 35),
        margin=dict(l=180, r=80),
        font=dict(family="Verdana"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.05),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Change 5: legend for thin data indicators
    st.caption(
        "Dashed/grey bars indicate indicative data (low base). "
        "Light grey bars indicate suppressed data — treat with caution."
    )

else:
    # ---- Bayesian Awareness Movement View ----
    st.subheader("Awareness Movement — Bayesian Change Detection")

    # Sidebar controls for evidence-based filtering
    st.sidebar.markdown("---")
    st.sidebar.subheader("Movement Detection")
    evidence_level = st.sidebar.select_slider(
        "Minimum evidence",
        options=["any", "weak", "moderate", "strong"],
        value="weak",
        format_func=lambda x: {
            "any": "Any (show all)",
            "weak": "Weak (80%)",
            "moderate": "Moderate (90%)",
            "strong": "Strong (95%)",
        }.get(x, x),
        key="evidence_slider",
    )
    mover_direction = st.sidebar.radio(
        "Direction", ["Both", "Gainers only", "Losers only"],
        horizontal=True, key="mover_direction",
    )
    top_n_movers = st.sidebar.slider(
        "Max brands per direction", 5, 30, 10, key="top_n_movers",
    )

    with st.spinner("Running Bayesian change detection..."):
        movers = calc_awareness_movers(
            df_main, level,
            period_a_months, period_b_months,
            min_evidence=evidence_level,
            top_n_each=top_n_movers,
        )

    if movers.empty:
        st.info(
            "No statistically significant awareness changes detected. "
            "This may indicate a stable market or insufficient sample size. "
            "Try lowering the evidence threshold or widening the comparison period."
        )
    else:
        # Filter by direction
        if mover_direction == "Gainers only":
            movers = movers[movers["direction"] == "gain"]
        elif mover_direction == "Losers only":
            movers = movers[movers["direction"] == "loss"]

        if movers.empty:
            st.info(f"No {mover_direction.lower().replace(' only', '')} detected at this threshold.")
        else:
            # Sort: gainers at top (positive change), losers at bottom
            movers = movers.sort_values("posterior_change_pp", ascending=True)

            # Colours and labels
            bar_colours = [
                CI_GREEN if d == "gain" else CI_RED
                for d in movers["direction"]
            ]
            evidence_icons = {
                "strong": "\u2605\u2605\u2605",
                "moderate": "\u2605\u2605",
                "weak": "\u2605",
                "none": "",
            }
            hover_text = [
                f"<b>{row['brand']}</b><br>"
                f"Change: {row['posterior_change_pp']:+.1f}pp<br>"
                f"95% CI: [{row['ci_lower_pp']:+.1f}, {row['ci_upper_pp']:+.1f}]pp<br>"
                f"P(gain): {row['prob_gain']:.0%} | P(loss): {row['prob_loss']:.0%}<br>"
                f"Evidence: {row['evidence_strength']}<br>"
                f"Period A: {row['n_mentions_a']:,} / {row['n_total_a']:,} ({row['rate_a']:.1%})<br>"
                f"Period B: {row['n_mentions_b']:,} / {row['n_total_b']:,} ({row['rate_b']:.1%})"
                for _, row in movers.iterrows()
            ]

            fig_mv = go.Figure()

            # Credible interval error bars
            error_right = [
                max(0, row["ci_upper_pp"] - row["posterior_change_pp"])
                for _, row in movers.iterrows()
            ]
            error_left = [
                max(0, row["posterior_change_pp"] - row["ci_lower_pp"])
                for _, row in movers.iterrows()
            ]

            fig_mv.add_trace(go.Bar(
                y=movers["brand"],
                x=movers["posterior_change_pp"],
                orientation="h",
                marker_color=bar_colours,
                error_x=dict(
                    type="data",
                    symmetric=False,
                    array=error_right,
                    arrayminus=error_left,
                    color=CI_GREY,
                    thickness=1.5,
                    width=3,
                ),
                text=[
                    f"{row['posterior_change_pp']:+.1f}pp  {evidence_icons.get(row['evidence_strength'], '')}"
                    for _, row in movers.iterrows()
                ],
                textposition="outside",
                textfont=dict(size=11, family="Verdana"),
                hovertext=hover_text,
                hoverinfo="text",
            ))

            # Zero reference line
            fig_mv.add_vline(
                x=0, line_dash="dot", line_color=CI_GREY, line_width=1,
            )

            fig_mv.update_layout(
                xaxis_title="Posterior mean change (pp) with 95% credible interval",
                height=max(400, len(movers) * 35),
                margin=dict(l=180, r=100),
                font=dict(family="Verdana"),
                plot_bgcolor="white",
                paper_bgcolor="white",
            )

            # Add probability annotations
            for _, row in movers.iterrows():
                prob = row["prob_gain"] if row["direction"] == "gain" else row["prob_loss"]
                fig_mv.add_annotation(
                    x=0,
                    y=row["brand"],
                    text=f"P={prob:.0%}",
                    showarrow=False,
                    font=dict(size=9, color=CI_GREY, family="Verdana"),
                    xanchor="right" if row["direction"] == "gain" else "left",
                    xshift=-8 if row["direction"] == "gain" else 8,
                )

            st.plotly_chart(fig_mv, use_container_width=True)

            # Legend
            st.caption(
                "Brands ranked by strength of statistical evidence for genuine awareness change. "
                "The Bayesian method accounts for sample size, so smaller brands appear when "
                "there is sufficient evidence. Error bars show 95% credible intervals. "
                "\u2605\u2605\u2605 = strong (95%+), \u2605\u2605 = moderate (90%+), \u2605 = weak (80%+)."
            )

# ---- Multi-Brand Trend Line Chart (Spec Section 9.6) ----
st.markdown("---")
st.subheader("Multi-Brand Awareness Trend")

# Compute per-brand per-month awareness rates
with st.spinner("Calculating awareness trends..."):
    trend_rates = calc_awareness_rates(df_main, level)

if not trend_rates.empty:
    # Filter options for trend chart
    trend_filter = st.radio(
        "Trend filter",
        ["Top 10 by current awareness", "Top 10 by market share", "Custom competitor set"],
        horizontal=True,
        key="trend_filter",
    )

    # Determine which brands to show
    latest_month = trend_rates["month"].max()
    latest_rates = trend_rates[trend_rates["month"] == latest_month].sort_values("rate", ascending=False)

    if trend_filter == "Top 10 by current awareness":
        selected_brands = latest_rates.head(10)["brand"].tolist()
    elif trend_filter == "Top 10 by market share":
        # Use mention count as proxy for market share
        selected_brands = latest_rates.sort_values("n_mentions", ascending=False).head(10)["brand"].tolist()
    else:
        # Custom competitor set
        all_trend_brands = sorted(trend_rates["brand"].unique().tolist())
        selected_brands = st.multiselect(
            "Select brands (max 30)",
            options=all_trend_brands,
            default=latest_rates.head(10)["brand"].tolist(),
            max_selections=30,
            key="trend_brands",
        )

    if selected_brands:
        trend_data = trend_rates[trend_rates["brand"].isin(selected_brands)].sort_values("month")
        awareness_selected_insurer = st.session_state.get("selected_insurer", "")

        fig_trend = go.Figure()
        for i, brand in enumerate(selected_brands):
            brand_data = trend_data[trend_data["brand"] == brand]
            if brand_data.empty:
                continue
            colour = BUMP_COLOURS[i % len(BUMP_COLOURS)]
            is_selected = brand == awareness_selected_insurer
            line_width = 4 if is_selected else 2
            marker_size = 8 if is_selected else 5
            x_labels = [format_year_month(m) for m in brand_data["month"]]
            fig_trend.add_trace(go.Scatter(
                x=x_labels,
                y=brand_data["rate"],
                mode="lines+markers",
                name=brand,
                line=dict(color=colour, width=line_width),
                marker=dict(size=marker_size, color=colour),
                hovertemplate=(
                    f"<b>{brand}</b><br>"
                    "Rate: %{y:.1%}<br>"
                    "%{x}<extra></extra>"
                ),
            ))

        q_code = "Q2" if level == "prompted" else "Q27"
        period_label = f"{format_year_month(trend_rates['month'].min())} to {format_year_month(trend_rates['month'].max())}"
        n_total = int(trend_rates[trend_rates["month"] == latest_month]["n_total"].iloc[0]) if not latest_rates.empty else 0

        trend_chart_title = f"Multi-Brand Awareness Trend — {trend_filter} ({level.title()})"

        apply_export_metadata(
            fig_trend,
            title=trend_chart_title,
            period=period_label,
            base=n_total,
            question=q_code,
        )

        fig_trend.update_layout(
            yaxis_tickformat=".0%",
            yaxis_title="Awareness Rate",
            yaxis_range=[0, 1],
            height=500,
            font=dict(family="Verdana"),
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        st.caption(f"Showing {len(selected_brands)} brands. Maximum 30 brands displayed.")
    else:
        st.info("Select at least one brand to display the trend chart.")
else:
    st.info("Insufficient data to build multi-brand trend chart.")

# ---- Footer caption ----
st.caption(caption)

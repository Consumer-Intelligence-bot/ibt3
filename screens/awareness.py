"""
Screen 1: Awareness & Consideration.

Merges Market Awareness (pages/5), Insurer Awareness (pages/6),
and Unprompted Awareness (pages/11) into a single screen with
Market/Insurer view toggle.

Sub-tabs: Prompted & Consideration | Unprompted (Q1)
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.awareness import (
    AWARENESS_LEVELS,
    calc_awareness_movers,
    calc_awareness_rates,
    calc_awareness_slopegraph,
    calc_dual_period_comparison,
    set_awareness_product,
)
from lib.analytics.demographics import apply_filters
from lib.analytics.spontaneous import (
    calc_salience_gap,
    calc_spontaneous_metrics,
    calc_toma_ranks,
    calc_toma_share,
)
from lib.chart_export import apply_export_metadata
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_panel
from lib.config import (
    BUMP_COLOURS,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_VIOLET,
    CI_WHITE,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import FONT, fmt_pct, section_divider, period_label
from lib.state import format_year_month, get_ss_data, render_dual_period_selector


def render(filters: dict):
    """Render the Awareness & Consideration screen."""
    df_motor, dimensions = get_ss_data()

    if df_motor.empty:
        st.warning("No data loaded. Go to Admin to refresh from Power BI.")
        return

    product = filters["product"]
    selected_months = filters["selected_months"]
    insurer = filters["insurer"]

    set_awareness_product(product)

    # Sub-view selector
    view = st.radio(
        "Awareness type",
        ["Prompted & Consideration", "Unprompted (Q1)"],
        horizontal=True,
        key="awareness_view_radio",
    )

    if view == "Unprompted (Q1)":
        _render_unprompted(df_motor, filters)
    else:
        _render_prompted(df_motor, filters)


def _render_prompted(df_motor, filters):
    """Prompted awareness and consideration view."""
    product = filters["product"]
    selected_months = filters["selected_months"]
    insurer = filters["insurer"]

    df_main = apply_filters(df_motor, product=product, selected_months=selected_months)
    if df_main.empty:
        st.warning("No data for selected filters.")
        return

    n = len(df_main)
    period = period_label(selected_months)

    # Awareness level toggle
    _product_levels = AWARENESS_LEVELS.get(product, AWARENESS_LEVELS.get("Motor", {}))
    available_levels = [l for l in ["prompted", "consideration"] if l in _product_levels]

    if not available_levels:
        st.warning("No awareness data available for this product.")
        return

    level = st.radio(
        "Awareness level",
        available_levels,
        format_func=lambda x: {
            "prompted": f"Prompted ({_product_levels.get('prompted', 'Q2')})",
            "consideration": f"Consideration ({_product_levels.get('consideration', 'Q27')})",
        }.get(x, x),
        horizontal=True,
        key="awareness_level_radio",
    )

    if insurer:
        _render_insurer_prompted(df_main, insurer, level, product, period, n)
    else:
        _render_market_prompted(df_main, level, product, period, n)


def _render_market_prompted(df_main, level, product, period, n):
    """Market-level prompted awareness."""
    st.subheader("Awareness: Market View")

    # Awareness rates by brand
    rates = calc_awareness_rates(df_main, level)
    if rates.empty:
        st.warning("No awareness data available for this level.")
        return

    # Latest month rates
    latest_month = rates["month"].max()
    latest = rates[rates["month"] == latest_month].sort_values("rate", ascending=False)

    section_divider("Current Awareness Ranking")

    # Top 10 bar chart
    top10 = latest.head(10)
    if not top10.empty:
        fig = go.Figure(go.Bar(
            x=top10["rate"],
            y=top10["brand"],
            orientation="h",
            marker_color=CI_MAGENTA,
            text=[f"{r:.0%}" for r in top10["rate"]],
            textposition="outside",
        ))
        fig.update_layout(
            xaxis_tickformat=".0%",
            height=max(300, len(top10) * 35 + 80),
            margin=dict(l=10, r=50, t=10, b=40),
            font=dict(family=FONT, size=11, color=CI_GREY),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Trend lines (top 5 brands)
    section_divider("Awareness Trends (Top 5)")

    top5_brands = latest.head(5)["brand"].tolist()
    trend_data = rates[rates["brand"].isin(top5_brands)]

    if not trend_data.empty:
        fig = go.Figure()
        for i, brand in enumerate(top5_brands):
            brand_data = trend_data[trend_data["brand"] == brand].sort_values("month")
            fig.add_trace(go.Scatter(
                x=[format_year_month(m) for m in brand_data["month"]],
                y=brand_data["rate"],
                mode="lines+markers",
                name=brand,
                line=dict(color=BUMP_COLOURS[i % len(BUMP_COLOURS)], width=2),
                marker=dict(size=4),
            ))
        fig.update_layout(
            height=350,
            yaxis=dict(title="Awareness Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Dual period comparison
    section_divider("Period Comparison")
    periods = render_dual_period_selector()
    if periods:
        comparison = calc_dual_period_comparison(
            df_main, level, periods["period_a_months"], periods["period_b_months"]
        )
        if comparison is not None and not comparison.empty:
            comparison = comparison.sort_values("change_pp", ascending=False).head(10)
            fig = go.Figure(go.Bar(
                x=comparison["change_pp"],
                y=comparison["brand"],
                orientation="h",
                marker_color=[CI_GREEN if c > 0 else CI_RED for c in comparison["change_pp"]],
                text=[f"{c:+.1f}pp" for c in comparison["change_pp"]],
                textposition="outside",
            ))
            fig.update_layout(
                height=max(300, len(comparison) * 30),
                margin=dict(l=10, r=60, t=10, b=40),
                font=dict(family=FONT, size=11, color=CI_GREY),
                plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
                yaxis=dict(autorange="reversed"),
                xaxis=dict(title="Change (pp)"),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(periods["caption"])
        else:
            st.info("Insufficient data for period comparison.")

    st.markdown("---")
    st.caption(f"Awareness | Market | {product} | {period} | n={n:,}")


def _render_insurer_prompted(df_main, insurer, level, product, period, n):
    """Insurer-level prompted awareness."""
    st.subheader(f"Awareness: {insurer}")

    rates = calc_awareness_rates(df_main, level)
    if rates.empty:
        st.warning("No awareness data available.")
        return

    # Insurer's awareness trend
    insurer_data = rates[rates["brand"] == insurer].sort_values("month")

    if insurer_data.empty:
        st.warning(f"No awareness data for {insurer}.")
        return

    # KPIs
    latest_month = rates["month"].max()
    latest_all = rates[rates["month"] == latest_month].sort_values("rate", ascending=False)
    ins_latest = latest_all[latest_all["brand"] == insurer]

    if not ins_latest.empty:
        ins_rate = ins_latest.iloc[0]["rate"]
        ins_rank = latest_all.index.get_loc(ins_latest.index[0]) + 1 if ins_latest.index[0] in latest_all.index else None

        col1, col2, col3 = st.columns(3)
        with col1:
            kpi_card(f"{insurer} Awareness", fmt_pct(ins_rate), f"n={n:,}", CI_MAGENTA)
        with col2:
            avg_rate = latest_all["rate"].mean()
            kpi_card("Market Average", fmt_pct(avg_rate), f"{len(latest_all)} brands", MARKET_COLOUR)
        with col3:
            kpi_card("Rank", f"{ins_rank}" if ins_rank else "\u2014", f"of {len(latest_all)} brands", CI_GREY)

    # Trend
    section_divider("Awareness Trend")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[format_year_month(m) for m in insurer_data["month"]],
        y=insurer_data["rate"],
        mode="lines+markers",
        name=insurer,
        line=dict(color=CI_MAGENTA, width=2),
    ))
    # Add market average line
    mkt_avg = rates.groupby("month")["rate"].mean().reset_index()
    fig.add_trace(go.Scatter(
        x=[format_year_month(m) for m in mkt_avg["month"]],
        y=mkt_avg["rate"],
        mode="lines",
        name="Market Avg",
        line=dict(color=CI_GREY, width=1, dash="dot"),
    ))
    fig.update_layout(
        height=300,
        yaxis=dict(title="Awareness Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=20, t=10, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Slopegraph
    section_divider("Slopegraph: Start vs End of Period")
    slopegraph = calc_awareness_slopegraph(df_main, insurer, level)
    if slopegraph is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            kpi_card("Start Rate", fmt_pct(slopegraph.get("start_rate")), format_year_month(slopegraph.get("start_month", 0)), CI_GREY)
        with col2:
            kpi_card("End Rate", fmt_pct(slopegraph.get("end_rate")), format_year_month(slopegraph.get("end_month", 0)), CI_MAGENTA)
        with col3:
            change = slopegraph.get("change", 0) * 100
            colour = CI_GREEN if change > 0 else CI_RED if change < 0 else CI_GREY
            kpi_card("Change", f"{change:+.1f}pp", "", colour)

    # --- AI Narrative ---
    section_divider("AI Narrative")
    ins_rate_val = ins_rate if not ins_latest.empty else 0
    rank_val = ins_rank if ins_rank else 0
    total_val = len(latest_all)
    slopegraph_data = calc_awareness_slopegraph(df_main, insurer, level)
    change_val = 0.0
    if slopegraph_data is not None:
        change_val = slopegraph_data.get("change", 0) * 100
    narrative = generate_screen_narrative("awareness", {
        "insurer": insurer,
        "product": product,
        "awareness_rate": ins_rate_val,
        "rank": rank_val,
        "total_brands": total_val,
        "change_pp": change_val,
    })
    render_narrative_panel(narrative, "awareness")

    # --- Cross-screen links ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Shopping Behaviour", key="awareness_to_shopping"):
            from lib.state import navigate_to
            navigate_to("shopping")
    with col2:
        if st.button("View Switching & Flows", key="awareness_to_switching"):
            from lib.state import navigate_to
            navigate_to("switching")

    st.markdown("---")
    st.caption(f"Awareness | {insurer} | {product} | {period} | n={n:,}")


def _render_unprompted(df_motor, filters):
    """Unprompted (Q1) awareness view."""
    product = filters["product"]
    selected_months = filters["selected_months"]

    if product == "Pet":
        st.info("Unprompted awareness is not available for Pet insurance.")
        return

    st.subheader("Unprompted Brand Awareness (Q1)")

    df_main = apply_filters(df_motor, product=product, selected_months=selected_months)
    if df_main.empty:
        st.warning("No data for selected filters.")
        return

    # Check for Q1 data
    q1_cols = [c for c in df_main.columns if c.startswith("Q1_") and not c.startswith("Q1_{")]
    if not q1_cols:
        st.warning("No Q1 spontaneous awareness data available.")
        return

    n = len(df_main)
    period = period_label(selected_months)

    with st.spinner("Computing spontaneous awareness metrics..."):
        metrics = calc_spontaneous_metrics(df_main)

    if metrics is None or metrics.empty:
        st.warning("Unable to compute Q1 metrics.")
        return

    # TOMA Share
    section_divider("Share of Mind (TOMA)")

    toma_share, top_brands = calc_toma_share(metrics)
    if toma_share is not None and not toma_share.empty and top_brands:
        if "month" in toma_share.columns:
            toma_share = toma_share.set_index("month")
        fig = go.Figure()
        for i, brand in enumerate(top_brands):
            if brand not in toma_share.columns:
                continue
            month_labels = [format_year_month(m) for m in toma_share.index]
            fig.add_trace(go.Scatter(
                x=month_labels,
                y=toma_share[brand],
                mode="lines",
                name=brand,
                stackgroup="one",
                line=dict(color=BUMP_COLOURS[i % len(BUMP_COLOURS)]),
            ))
        fig.update_layout(
            height=400,
            yaxis=dict(title="Share of TOMA", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # TOMA Rankings (Bump chart)
    section_divider("TOMA Rankings")

    toma_ranks, rank_top_brands = calc_toma_ranks(metrics)
    if toma_ranks is not None and not toma_ranks.empty and rank_top_brands:
        if "month" in toma_ranks.columns:
            toma_ranks = toma_ranks.set_index("month")
        fig = go.Figure()
        for i, brand in enumerate(rank_top_brands):
            if brand not in toma_ranks.columns:
                continue
            month_labels = [format_year_month(m) for m in toma_ranks.index]
            fig.add_trace(go.Scatter(
                x=month_labels,
                y=toma_ranks[brand],
                mode="lines+markers",
                name=brand,
                line=dict(color=BUMP_COLOURS[i % len(BUMP_COLOURS)], width=2),
                marker=dict(size=5),
            ))
        fig.update_layout(
            height=400,
            yaxis=dict(title="Rank", autorange="reversed", gridcolor=CI_LIGHT_GREY),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Salience Gap
    section_divider("Salience Gap: Total Awareness vs TOMA")

    salience = calc_salience_gap(metrics)
    if salience is not None and not salience.empty:
        fig = go.Figure(go.Scatter(
            x=salience["mention_pct"],
            y=salience["toma_pct"],
            mode="markers+text",
            text=salience["brand"],
            textposition="top center",
            marker=dict(size=10, color=CI_MAGENTA),
            textfont=dict(size=9, family=FONT),
        ))
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dot", color=CI_GREY))
        fig.update_layout(
            height=400,
            xaxis=dict(title="Total Mention Rate", tickformat=".0%"),
            yaxis=dict(title="TOMA Rate", tickformat=".0%"),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Brands above the diagonal have disproportionately high top-of-mind awareness relative to total mentions.")

    st.markdown("---")
    st.caption(f"Unprompted Awareness | Market | {product} | {period} | n={n:,}")

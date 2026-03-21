"""
Screen 2: Pre-Renewal Context.

Market View: Price direction distribution (Q6), price change bands (Q6a/Q6b),
             tenure distribution (Q21), price-to-shopping crossover.
Insurer View: Same metrics for the selected insurer vs market.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.pre_renewal import (
    calc_tenure_distribution,
    calc_price_shopping_crossover,
    calc_tenure_retention_crossover,
)
from lib.analytics.price import (
    calc_price_direction_dist,
    calc_price_magnitude_dist,
    calc_rate_by_price_direction,
)
from lib.analytics.rates import calc_shopping_rate
from lib.chart_export import render_suppression_html
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_panel
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    CI_YELLOW,
    CI_VIOLET,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT
from lib.state import get_ss_data


_DIRECTION_COLOURS = {
    "Higher": CI_RED,
    "Lower": CI_GREEN,
    "Unchanged": CI_GREY,
    "New": CI_YELLOW,
}


def render(filters: dict):
    """Render the Pre-Renewal Context screen."""
    df_motor, dimensions = get_ss_data()

    if df_motor.empty:
        st.warning("No data loaded. Go to Admin to refresh from Power BI.")
        return

    insurer = filters["insurer"]
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

    if df_mkt.empty:
        st.warning("No data for selected filters.")
        return

    period = period_label(selected_months)
    n_mkt = len(df_mkt)

    if insurer:
        _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt)
    else:
        _render_market_view(df_mkt, filters, period, n_mkt)


def _render_market_view(df_mkt, filters, period, n_mkt):
    """Market-level pre-renewal context."""
    st.subheader("Pre-Renewal Context: Market View")

    # --- Price Direction Distribution (Q6) ---
    section_divider("Price Direction at Renewal (Q6)")
    st.caption("Q6: Was your renewal price higher, lower, or about the same?")

    price_dist = calc_price_direction_dist(df_mkt)
    if price_dist is not None:
        _render_price_direction_chart(price_dist, "Market")
    else:
        st.info("No Q6 data available.")

    # --- Price Change Bands (Q6a / Q6b) ---
    section_divider("Price Change Magnitude (Q6a / Q6b)")

    col_higher, col_lower = st.columns(2)

    with col_higher:
        st.markdown("**Higher by how much? (Q6a)**")
        higher_bands = calc_price_magnitude_dist(df_mkt, "Higher")
        if higher_bands is not None:
            _render_band_chart(higher_bands, CI_RED, "Higher")
        else:
            st.info("No Q6a data available.")

    with col_lower:
        st.markdown("**Lower by how much? (Q6b)**")
        lower_bands = calc_price_magnitude_dist(df_mkt, "Lower")
        if lower_bands is not None:
            _render_band_chart(lower_bands, CI_GREEN, "Lower")
        else:
            st.info("No Q6b data available.")

    # --- Price to Shopping Crossover ---
    section_divider("Price Direction vs Shopping Rate")

    crossover = calc_price_shopping_crossover(df_mkt)
    if crossover is not None and not crossover.empty:
        _render_crossover_chart(crossover)
    else:
        st.info("Insufficient data for price-to-shopping crossover.")

    # --- Tenure Distribution (Q21) ---
    section_divider("Tenure with Current Insurer (Q21)")

    tenure = calc_tenure_distribution(df_mkt)
    if tenure is not None:
        _render_tenure_chart(tenure)
    else:
        st.info("No Q21 tenure data available.")

    # --- Tenure vs Retention ---
    section_divider("Tenure vs Retention Rate")

    tenure_ret = calc_tenure_retention_crossover(df_mkt)
    if tenure_ret is not None and not tenure_ret.empty:
        fig = go.Figure(go.Bar(
            x=tenure_ret["tenure"],
            y=tenure_ret["retention_rate"],
            marker_color=CI_MAGENTA,
            text=[f"{r:.0%}" for r in tenure_ret["retention_rate"]],
            textposition="outside",
            hovertemplate="Tenure: %{x}<br>Retention: %{y:.1%}<br>n=%{customdata:,}<extra></extra>",
            customdata=tenure_ret["n"],
        ))
        fig.update_layout(
            height=300,
            yaxis=dict(title="Retention Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            xaxis=dict(title="Tenure"),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient data for tenure-retention crossover.")

    # Footer
    st.markdown("---")
    st.caption(f"Pre-Renewal Context | Market | {filters['product']} | {period} | n={n_mkt:,}")


def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer-level pre-renewal context vs market."""
    product = filters["product"]
    selected_months = filters["selected_months"]

    df_ins = apply_filters(
        df_motor,
        insurer=insurer,
        age_band=filters["age_band"],
        region=filters["region"],
        payment_type=filters["payment_type"],
        product=product,
        selected_months=selected_months,
    )

    n_ins = len(df_ins)

    st.subheader(f"Pre-Renewal Context: {insurer}")

    st.markdown(
        f'<div style="background:{CI_LIGHT_GREY}; padding:10px 16px; border-radius:4px; '
        f'font-family:{FONT}; font-size:13px; color:{CI_GREY}; margin-bottom:16px;">'
        f"<b>{insurer}</b> &nbsp;|&nbsp; {product} &nbsp;|&nbsp; {period} "
        f"&nbsp;|&nbsp; Insurer n={n_ins:,} &nbsp;|&nbsp; Market n={n_mkt:,}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if n_ins < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # --- Price Direction: insurer vs market ---
    section_divider("Price Direction at Renewal (Q6)")

    ins_dist = calc_price_direction_dist(df_ins)
    mkt_dist = calc_price_direction_dist(df_mkt)

    if ins_dist is not None and mkt_dist is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{insurer}**")
            _render_price_direction_chart(ins_dist, insurer)
        with col2:
            st.markdown("**Market**")
            _render_price_direction_chart(mkt_dist, "Market")
    elif ins_dist is not None:
        _render_price_direction_chart(ins_dist, insurer)
    else:
        st.info("No Q6 data available.")

    # --- Price-Shopping Crossover ---
    section_divider("Price Direction vs Shopping Rate")

    ins_crossover = calc_price_shopping_crossover(df_ins)
    mkt_crossover = calc_price_shopping_crossover(df_mkt)

    if ins_crossover is not None and mkt_crossover is not None:
        # Merge for comparison
        merged = ins_crossover.merge(
            mkt_crossover, on="direction", suffixes=("_ins", "_mkt"), how="outer"
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=merged["direction"],
            y=merged["shopping_rate_ins"],
            name=insurer,
            marker_color=CI_VIOLET,
            text=[f"{r:.0%}" if pd.notna(r) else "" for r in merged["shopping_rate_ins"]],
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            x=merged["direction"],
            y=merged["shopping_rate_mkt"],
            name="Market",
            marker_color=CI_GREY,
            opacity=0.5,
            text=[f"{r:.0%}" if pd.notna(r) else "" for r in merged["shopping_rate_mkt"]],
            textposition="outside",
        ))
        fig.update_layout(
            barmode="group",
            height=300,
            yaxis=dict(title="Shopping Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1, xanchor="right"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient data for price-shopping crossover.")

    # --- Tenure ---
    section_divider("Tenure with Current Insurer (Q21)")

    ins_tenure = calc_tenure_distribution(df_ins)
    if ins_tenure is not None:
        _render_tenure_chart(ins_tenure)
    else:
        st.info("No Q21 tenure data available for this insurer.")

    # --- AI Narrative ---
    section_divider("AI Narrative")
    ins_price = calc_price_direction_dist(df_ins)
    pct_h = float(ins_price.get("Higher", 0)) if ins_price is not None else 0
    pct_l = float(ins_price.get("Lower", 0)) if ins_price is not None else 0
    pct_u = float(ins_price.get("Unchanged", 0)) if ins_price is not None else 0
    ins_cross = calc_price_shopping_crossover(df_ins)
    higher_shop = "N/A"
    if ins_cross is not None and not ins_cross.empty:
        h_row = ins_cross[ins_cross["direction"] == "Higher"]
        if not h_row.empty and h_row.iloc[0]["shopping_rate"] is not None:
            higher_shop = f"{h_row.iloc[0]['shopping_rate']:.0%}"
    narrative = generate_screen_narrative("pre_renewal", {
        "insurer": insurer,
        "product": filters["product"],
        "pct_higher": pct_h,
        "pct_lower": pct_l,
        "pct_unchanged": pct_u,
        "higher_shopping_rate": higher_shop,
    })
    render_narrative_panel(narrative, "pre_renewal")

    # --- Cross-screen links ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Shopping Behaviour", key="prerenewal_to_shopping"):
            from lib.state import navigate_to
            navigate_to("shopping")
    with col2:
        if st.button("View Switching & Flows", key="prerenewal_to_switching"):
            from lib.state import navigate_to
            navigate_to("switching")

    # Footer
    st.markdown("---")
    st.caption(
        f"Pre-Renewal Context | {insurer} | {filters['product']} | {period} | "
        f"Insurer n={n_ins:,} | Market n={n_mkt:,}"
    )


def _render_price_direction_chart(dist: pd.Series, label: str):
    """Render a horizontal bar chart for price direction distribution."""
    colours = [_DIRECTION_COLOURS.get(d, CI_GREY) for d in dist.index]

    fig = go.Figure(go.Bar(
        x=dist.values,
        y=dist.index,
        orientation="h",
        marker_color=colours,
        text=[f"{v:.0%}" for v in dist.values],
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_tickformat=".0%",
        height=200,
        margin=dict(l=10, r=40, t=10, b=20),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_band_chart(bands: pd.Series, colour: str, direction: str):
    """Render a bar chart for price change magnitude bands."""
    fig = go.Figure(go.Bar(
        x=bands.index.astype(str),
        y=bands.values,
        marker_color=colour,
        text=[f"{v:.0%}" for v in bands.values],
        textposition="outside",
    ))
    fig.update_layout(
        yaxis_tickformat=".0%",
        height=250,
        margin=dict(l=10, r=20, t=10, b=40),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_crossover_chart(crossover: pd.DataFrame):
    """Render price direction vs shopping rate grouped bar."""
    colours = [_DIRECTION_COLOURS.get(d, CI_GREY) for d in crossover["direction"]]

    fig = go.Figure(go.Bar(
        x=crossover["direction"],
        y=crossover["shopping_rate"],
        marker_color=colours,
        text=[f"{r:.0%}" if r is not None else "" for r in crossover["shopping_rate"]],
        textposition="outside",
        hovertemplate="Direction: %{x}<br>Shopping Rate: %{y:.1%}<br>n=%{customdata:,}<extra></extra>",
        customdata=crossover["n"],
    ))
    fig.update_layout(
        height=300,
        yaxis=dict(title="Shopping Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
        xaxis=dict(title="Price Direction at Renewal"),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=20, t=10, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_tenure_chart(tenure: pd.Series):
    """Render tenure distribution bar chart."""
    fig = go.Figure(go.Bar(
        x=tenure.index.astype(str),
        y=tenure.values,
        marker_color=CI_MAGENTA,
        text=[f"{v:.0%}" for v in tenure.values],
        textposition="outside",
    ))
    fig.update_layout(
        yaxis_tickformat=".0%",
        height=300,
        xaxis=dict(title="Years with current insurer"),
        margin=dict(l=10, r=20, t=10, b=40),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
    )
    st.plotly_chart(fig, use_container_width=True)

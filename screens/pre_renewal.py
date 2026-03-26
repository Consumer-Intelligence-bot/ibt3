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
    merge_tenure_mid_buckets,
    calc_price_shopping_crossover,
    calc_tenure_retention_crossover,
)
from lib.analytics.price import (
    calc_price_direction_dist,
    calc_price_direction_index,
    calc_price_magnitude_dist,
    calc_rate_by_price_direction,
    calc_avg_price_change,
    calc_price_change_comparison,
    calc_price_change_by_demo,
    BAND_MIDPOINTS,
)
from lib.analytics.flow_display import format_price_change
from lib.analytics.rates import calc_shopping_rate
from lib.chart_export import render_suppression_html
from lib.components.context_bar import render_context_bar
from lib.components.context_footer import render_context_footer
from lib.components.decision_kpi import decision_kpi_row
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_compact
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
from lib.formatting import fmt_pct, period_label, FONT
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

    # Sub-view selector
    view = st.radio(
        "View",
        ["Overview", "Price Analysis"],
        horizontal=True,
        key="prerenewal_view_radio",
    )

    if view == "Price Analysis":
        if insurer:
            _render_price_analysis_brand(df_mkt, insurer, filters, period, n_mkt)
        else:
            _render_price_analysis_market(df_mkt, filters, period, n_mkt)
    elif insurer:
        _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt)
    else:
        _render_market_view(df_mkt, filters, period, n_mkt)


def _render_market_view(df_mkt, filters, period, n_mkt):
    """Market-level pre-renewal context."""
    render_context_bar(
        "Pre-Renewal Context",
        product=filters["product"],
        period=period,
        n_market=n_mkt,
    )

    # --- KPIs: % Higher, % Lower, % Unchanged from price_dist ---
    price_dist = calc_price_direction_dist(df_mkt)
    if price_dist is not None:
        pct_h = float(price_dist.get("Higher", 0))
        pct_l = float(price_dist.get("Lower", 0))
        pct_u = float(price_dist.get("Unchanged", 0))
        decision_kpi_row([
            {"title": "% Higher", "value": fmt_pct(pct_h), "colour": CI_RED},
            {"title": "% Lower", "value": fmt_pct(pct_l), "colour": CI_GREEN},
            {"title": "% Unchanged", "value": fmt_pct(pct_u), "colour": CI_GREY},
        ])

    # --- Price Direction ---
    if price_dist is not None:
        st.markdown("**Price Direction at Renewal (Q6)**")
        _render_price_direction_chart(price_dist, "Market")
    else:
        st.info("No Q6 data available.")

    # --- Two-column: Crossover + Tenure ---
    col_crossover, col_tenure = st.columns(2)

    with col_crossover:
        crossover = calc_price_shopping_crossover(df_mkt)
        if crossover is not None and not crossover.empty:
            st.markdown("**Price Direction vs Shopping Rate**")
            _render_crossover_chart(crossover)

    with col_tenure:
        tenure = calc_tenure_distribution(df_mkt)
        if tenure is not None:
            tenure = merge_tenure_mid_buckets(tenure)
            st.markdown("**Tenure with Current Insurer (Q21)**")
            _render_tenure_chart(tenure)
        else:
            st.info("No Q21 tenure data available.")

    # --- Price Change Bands (Q6a / Q6b) - below the main layout ---
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

    # --- Tenure vs Retention ---
    tenure_ret = calc_tenure_retention_crossover(df_mkt)
    if tenure_ret is not None and not tenure_ret.empty:
        st.markdown("**Tenure vs Retention Rate**")
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

    # Footer
    render_context_footer(
        screen_name="pre_renewal_market",
        product=filters["product"],
        period=period,
        sample_n=n_mkt,
    )


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

    render_context_bar(
        "Pre-Renewal Context",
        insurer=insurer,
        product=product,
        period=period,
        n_insurer=n_ins,
        n_market=n_mkt,
    )

    # Suppression check
    if n_ins < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # --- AI Narrative (at top) ---
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
    render_narrative_compact(narrative, "pre_renewal")

    # --- KPIs: % Higher, % Lower, % Unchanged (with market comparison) ---
    mkt_price = calc_price_direction_dist(df_mkt)
    mkt_h = float(mkt_price.get("Higher", 0)) if mkt_price is not None else None
    mkt_l = float(mkt_price.get("Lower", 0)) if mkt_price is not None else None
    mkt_u = float(mkt_price.get("Unchanged", 0)) if mkt_price is not None else None

    def _pp_change(ins_val: float, mkt_val: float | None) -> str | None:
        if mkt_val is None:
            return None
        diff = (ins_val - mkt_val) * 100
        return f"{diff:+.1f}pp vs market"

    decision_kpi_row([
        {"title": "% Higher", "value": fmt_pct(pct_h), "colour": CI_RED,
         "change": _pp_change(pct_h, mkt_h), "sample_n": n_ins},
        {"title": "% Lower", "value": fmt_pct(pct_l), "colour": CI_GREEN,
         "change": _pp_change(pct_l, mkt_l), "sample_n": n_ins},
        {"title": "% Unchanged", "value": fmt_pct(pct_u), "colour": CI_GREY,
         "change": _pp_change(pct_u, mkt_u), "sample_n": n_ins},
    ])

    # --- Price Direction Index ---
    mkt_dist = calc_price_direction_dist(df_mkt)

    if ins_price is not None and mkt_dist is not None:
        index_df = calc_price_direction_index(ins_price, mkt_dist)
        if index_df is not None:
            st.markdown(f"**Price Direction Index: {insurer} vs Market (pp)**")
            _render_price_direction_index_chart(index_df)
        else:
            _render_price_direction_chart(ins_price, insurer)
    elif ins_price is not None:
        _render_price_direction_chart(ins_price, insurer)
    else:
        st.info("No Q6 data available.")

    # --- Two-column: Crossover + Tenure ---
    col_crossover, col_tenure = st.columns(2)

    with col_crossover:
        mkt_crossover = calc_price_shopping_crossover(df_mkt)

        if ins_cross is not None and mkt_crossover is not None:
            st.markdown("**Price Direction vs Shopping Rate**")
            merged = ins_cross.merge(
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

    with col_tenure:
        ins_tenure = calc_tenure_distribution(df_ins)
        if ins_tenure is not None:
            ins_tenure = merge_tenure_mid_buckets(ins_tenure)
            st.markdown("**Tenure with Current Insurer (Q21)**")
            _render_tenure_chart(ins_tenure)
        else:
            st.info("No Q21 tenure data available for this insurer.")

        # Cross-screen links
        st.markdown("**Related screens**")
        if st.button("View Shopping Behaviour", key="prerenewal_to_shopping"):
            from lib.state import navigate_to
            navigate_to("shopping")
        if st.button("View Switching & Flows", key="prerenewal_to_switching"):
            from lib.state import navigate_to
            navigate_to("switching")

    # Footer
    render_context_footer(
        screen_name="pre_renewal_insurer",
        product=product,
        period=period,
        sample_n=n_ins,
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


def _render_price_direction_index_chart(index_df: pd.DataFrame):
    """Render pp-deviation index chart: insurer minus market for each direction."""
    colours = [
        CI_RED if d > 0 else CI_GREEN if d < 0 else CI_GREY
        for d in index_df["diff_pp"]
    ]
    hover_text = [
        f"{row['direction']}<br>Insurer: {row['insurer_pct']:.1f}%<br>"
        f"Market: {row['market_pct']:.1f}%<br>Diff: {row['diff_pp']:+.1f}pp"
        for _, row in index_df.iterrows()
    ]
    fig = go.Figure(go.Bar(
        x=index_df["direction"],
        y=index_df["diff_pp"],
        marker_color=colours,
        text=[f"{d:+.1f}pp" for d in index_df["diff_pp"]],
        textposition="outside",
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_text,
    ))
    fig.add_hline(y=0, line_width=1, line_color=CI_GREY)
    fig.update_layout(
        height=250,
        yaxis=dict(title="Difference vs Market (pp)", gridcolor=CI_LIGHT_GREY),
        xaxis=dict(title="Price Direction"),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=20, t=10, b=40),
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
        height=280,
        bargap=0.15,
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


# ---------------------------------------------------------------------------
# Price Analysis sub-tab
# ---------------------------------------------------------------------------

def _render_price_analysis_market(df_mkt, filters, period, n_mkt):
    """Market-level price change analysis using midpoint mapping."""
    render_context_bar(
        "Price Analysis",
        product=filters["product"],
        period=period,
        n_market=n_mkt,
    )

    # --- Direction donut ---
    st.markdown("**Price Direction at Renewal**")

    price_dist = calc_price_direction_dist(df_mkt)
    if price_dist is not None:
        colours = [_DIRECTION_COLOURS.get(d, CI_GREY) for d in price_dist.index]
        fig = go.Figure(go.Pie(
            labels=price_dist.index,
            values=price_dist.values,
            hole=0.45,
            marker=dict(colors=colours),
            textinfo="label+percent",
            textfont=dict(family=FONT, size=11),
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family=FONT, size=11, color=CI_GREY),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No price direction data available.")

    # --- Band distribution (signed) ---
    st.markdown("**Price Change Distribution (Signed Bands)**")
    _render_signed_band_chart(df_mkt)

    # --- Average change KPI ---
    st.markdown("**Average Price Change**")
    avg = calc_avg_price_change(df_mkt)
    if avg is not None:
        change = avg["avg_change"]
        colour = CI_RED if change > 0 else CI_GREEN if change < 0 else CI_GREY
        col1, col2 = st.columns(2)
        with col1:
            kpi_card("Avg Price Change", format_price_change(change), f"n={avg['n']:,}", colour)
        with col2:
            kpi_card("Respondents with Band Data", f"{avg['n']:,}", f"Market total: {n_mkt:,}", CI_GREY)
    else:
        st.info("Insufficient data to compute average price change.")

    render_context_footer(
        screen_name="price_analysis_market",
        product=filters["product"],
        period=period,
        sample_n=n_mkt,
    )


def _render_price_analysis_brand(df_mkt, insurer, filters, period, n_mkt):
    """Brand-level price change analysis vs market."""
    has_pre_renewal = "PreRenewalCompany" in df_mkt.columns
    if not has_pre_renewal:
        st.warning("PreRenewalCompany column not available. Cannot filter by brand.")
        return

    n_brand = int((df_mkt["PreRenewalCompany"] == insurer).sum())

    render_context_bar(
        f"{insurer}'s Pre-Renewal Price Analysis",
        insurer=insurer,
        product=filters["product"],
        period=period,
        n_insurer=n_brand,
        n_market=n_mkt,
    )

    if n_brand < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_brand, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # --- Direction stacked bar: brand vs others ---
    st.markdown("**Price Direction: Brand vs Others**")

    comparison = calc_price_change_comparison(df_mkt, insurer)
    if comparison is not None:
        brand_split = comparison["brand"]["direction_split"]
        others_split = comparison["others"]["direction_split"] if comparison["others"] else pd.Series(dtype=float)

        # Normalise to percentages
        brand_pcts = brand_split / brand_split.sum() if brand_split.sum() > 0 else brand_split
        others_pcts = others_split / others_split.sum() if others_split.sum() > 0 else others_split

        directions = ["Higher", "Lower", "Unchanged", "New"]
        fig = go.Figure()
        for d in directions:
            fig.add_trace(go.Bar(
                x=[insurer, "Others"],
                y=[brand_pcts.get(d, 0), others_pcts.get(d, 0)],
                name=d,
                marker_color=_DIRECTION_COLOURS.get(d, CI_GREY),
                text=[f"{brand_pcts.get(d, 0):.0%}", f"{others_pcts.get(d, 0):.0%}"],
                textposition="inside",
            ))
        fig.update_layout(
            barmode="stack",
            height=300,
            yaxis=dict(tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Average change KPI: brand vs market ---
    st.markdown("**Average Price Change**")
    brand_avg = calc_avg_price_change(df_mkt, brand=insurer)
    market_avg = calc_avg_price_change(df_mkt)

    if brand_avg is not None and market_avg is not None:
        col1, col2 = st.columns(2)
        with col1:
            bc = brand_avg["avg_change"]
            colour = CI_RED if bc > 0 else CI_GREEN if bc < 0 else CI_GREY
            kpi_card(f"{insurer} Avg Change", format_price_change(bc), f"n={brand_avg['n']:,}", colour)
        with col2:
            mc = market_avg["avg_change"]
            colour = CI_RED if mc > 0 else CI_GREEN if mc < 0 else CI_GREY
            kpi_card("Market Avg Change", format_price_change(mc), f"n={market_avg['n']:,}", colour)
    else:
        st.info("Insufficient data for average price change comparison.")

    # --- Demographic breakdown (side by side) ---
    st.markdown("**Price Change by Demographic**")

    demo_cols = {"AgeBand": "Age Band", "Region": "Region"}
    demo_items = []
    for col, label in demo_cols.items():
        if col not in df_mkt.columns:
            continue
        demo = calc_price_change_by_demo(df_mkt, col, brand=insurer)
        if demo is not None and not demo.empty:
            demo_items.append((label, demo))

    if demo_items:
        cols = st.columns(len(demo_items))
        for col_st, (label, demo) in zip(cols, demo_items):
            with col_st:
                st.markdown(f"**{label}**")
                header = (
                    f'<table style="width:100%; font-family:{FONT}; font-size:12px; '
                    f'border-collapse:collapse; margin-bottom:12px;">'
                    f'<tr style="border-bottom:2px solid {CI_GREY};">'
                    f'<th style="text-align:left; padding:6px;">{label}</th>'
                    f'<th style="text-align:right; padding:6px;">Avg Change</th>'
                    f'<th style="text-align:right; padding:6px;">n</th></tr>'
                )
                rows_html = []
                for _, row in demo.iterrows():
                    avg_c = row["avg_change"]
                    sign = "+" if avg_c > 0 else ""
                    colour = CI_RED if avg_c > 0 else CI_GREEN if avg_c < 0 else CI_GREY
                    n_str = f"{int(row['n']):,}"
                    if row["flag_low_n"]:
                        n_str += " *"
                        colour = CI_GREY
                    rows_html.append(
                        f'<tr style="border-bottom:1px solid {CI_LIGHT_GREY};">'
                        f'<td style="padding:5px 6px;">{row["group"]}</td>'
                        f'<td style="text-align:right; padding:5px 6px; color:{colour}; font-weight:bold;">'
                        f'{sign}{abs(avg_c):.0f}</td>'
                        f'<td style="text-align:right; padding:5px 6px;">{n_str}</td></tr>'
                    )
                st.markdown(header + "".join(rows_html) + "</table>", unsafe_allow_html=True)
                if demo["flag_low_n"].any():
                    st.caption("* n < 30: treat with caution.")

    render_context_footer(
        screen_name="price_analysis_brand",
        product=filters["product"],
        period=period,
        sample_n=n_brand,
    )


def _render_signed_band_chart(df: pd.DataFrame):
    """Render a combined signed band distribution chart (Q6a + Q6b)."""
    if "Q6a" not in df.columns and "Q6b" not in df.columns:
        st.info("No Q6a/Q6b band data available.")
        return

    rows = []
    # Higher bands (positive)
    if "Q6a" in df.columns:
        higher = df[df["PriceDirection"] == "Higher"]
        for band, mid in BAND_MIDPOINTS.items():
            n = int((higher["Q6a"] == band).sum())
            if n > 0:
                rows.append({"band": band, "midpoint": mid, "n": n})

    # Lower bands (negative)
    if "Q6b" in df.columns:
        lower = df[df["PriceDirection"] == "Lower"]
        for band, mid in BAND_MIDPOINTS.items():
            n = int((lower["Q6b"] == band).sum())
            if n > 0:
                rows.append({"band": band, "midpoint": -mid, "n": n})

    if not rows:
        st.info("No band data available.")
        return

    band_df = pd.DataFrame(rows).sort_values("midpoint")
    total = band_df["n"].sum()
    band_df["pct"] = band_df["n"] / total

    colours = [CI_GREEN if m < 0 else CI_RED for m in band_df["midpoint"]]
    labels = [f"-{b}" if m < 0 else f"+{b}" for b, m in zip(band_df["band"], band_df["midpoint"])]

    fig = go.Figure(go.Bar(
        x=band_df["midpoint"],
        y=band_df["pct"],
        marker_color=colours,
        text=[f"{p:.0%}" for p in band_df["pct"]],
        textposition="outside",
        hovertemplate="%{customdata}: %{y:.1%}<extra></extra>",
        customdata=labels,
    ))
    fig.update_layout(
        height=300,
        bargap=0.05,
        xaxis=dict(title="Price Change (£, midpoint)", gridcolor=CI_LIGHT_GREY),
        yaxis=dict(title="% of Respondents", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=20, t=10, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

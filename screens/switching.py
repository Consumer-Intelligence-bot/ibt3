"""
Screen 5: Switching & Flows.

Market View: Switching rate trend, flow matrix overview, top movers.
Insurer View: Net flow, top sources/destinations, flow index, departed sentiment.
Combines content from pages/2 (flows section), pages/10 (flow intelligence).

Layout: Decision Screen pattern (context bar, narrative, KPIs, 70/30 split, footer).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.demographics import apply_filters
from lib.analytics.flows import (
    calc_flow_index,
    calc_flow_matrix,
    calc_net_flow,
    calc_top_destinations,
    calc_top_sources,
    calc_departed_sentiment,
    calc_market_departed_sentiment,
)
from lib.analytics.flow_display import (
    format_flow_pct,
    format_net_flow_pct,
    get_index_bar_colour,
    kpi_vs_market_colour,
)
from lib.analytics.rates import (
    calc_retention_rate,
    calc_rolling_switching_trend,
    calc_shopping_rate,
    calc_switching_rate,
)
from lib.chart_export import render_suppression_html
from lib.components.context_bar import render_context_bar
from lib.components.context_footer import render_context_footer
from lib.components.decision_kpi import decision_kpi, decision_kpi_row, render_kpi_with_info
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_compact
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    FONT,
    MARKET_COLOUR,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, period_label
from lib.state import get_ss_data


def render(filters: dict):
    """Render the Switching & Flows screen."""
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
        _render_market_view(df_motor, df_mkt, filters, period, n_mkt)


# ---------------------------------------------------------------------------
# Market view
# ---------------------------------------------------------------------------

def _render_market_view(df_motor, df_mkt, filters, period, n_mkt):
    """Market-level switching and flows overview."""
    product = filters["product"]

    # ── Calculate rates ──────────────────────────────────────────
    switching_rate = calc_switching_rate(df_mkt)
    retention_rate = calc_retention_rate(df_mkt)
    shopping_rate = calc_shopping_rate(df_mkt)

    # ── Context bar ──────────────────────────────────────────────
    render_context_bar(
        "Switching & Flows",
        product=product,
        period=period,
        n_market=n_mkt,
    )

    # ── KPI row ──────────────────────────────────────────────────
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    with kpi_col1:
        render_kpi_with_info(
            {
                "title": "Switching Rate",
                "value": fmt_pct(switching_rate),
                "sample_n": n_mkt,
                "colour": CI_GREY,
            },
            "% of customers who changed insurer at renewal. Lower = better retention.",
        )
    with kpi_col2:
        render_kpi_with_info(
            {
                "title": "Retention Rate",
                "value": fmt_pct(retention_rate),
                "sample_n": n_mkt,
                "colour": CI_GREY,
            },
            "% of customers who stayed with their insurer at renewal.",
        )
    with kpi_col3:
        render_kpi_with_info(
            {
                "title": "Shopping Rate",
                "value": fmt_pct(shopping_rate),
                "sample_n": n_mkt,
                "colour": CI_GREY,
            },
            "% of customers who compared quotes from other insurers, regardless of whether they switched.",
        )

    # ── 70 / 30 split ───────────────────────────────────────────
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Smoothing toggle
        smoothing = st.radio(
            "Smoothing",
            ["Monthly", "3-month rolling"],
            horizontal=True,
            key="switching_trend_smoothing",
        )
        window = 3 if smoothing == "3-month rolling" else 1

        # Switching rate trend
        if "RenewalYearMonth" in df_mkt.columns:
            trend_df = calc_rolling_switching_trend(df_mkt, window=window)

            if not trend_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=trend_df["label"],
                    y=trend_df["switching_rate"],
                    mode="lines+markers",
                    line=dict(color=CI_MAGENTA, width=2),
                    marker=dict(size=5),
                    hovertemplate="<b>%{x}</b><br>Switching: %{y:.1%}<extra></extra>",
                ))
                fig.update_layout(
                    height=300,
                    yaxis=dict(title="Switching Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
                    xaxis=dict(title="", gridcolor=CI_LIGHT_GREY),
                    plot_bgcolor=CI_WHITE,
                    paper_bgcolor=CI_WHITE,
                    font=dict(family=FONT, size=11, color=CI_GREY),
                    margin=dict(l=10, r=20, t=10, b=40),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Insufficient monthly data for trend.")

    with col_secondary:
        # Flow matrix summary (top movers)
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin-bottom:8px;">Top Movers</div>',
            unsafe_allow_html=True,
        )

        flow_mat = calc_flow_matrix(df_mkt)
        if not flow_mat.empty:
            row_totals = flow_mat.sum(axis=1).sort_values(ascending=False)
            total_flow = int(row_totals.sum())
            top_insurers = row_totals.head(8).index.tolist()
            for ins_name in top_insurers:
                vol = int(row_totals[ins_name])
                pct_str = format_flow_pct(vol, total_flow) or "—"
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:4px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'<span style="color:{CI_GREY};">{ins_name}</span>'
                    f'<span style="float:right; font-weight:700; color:{CI_MAGENTA};">{pct_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.caption(f"% of total switching volume. Cells < {MIN_BASE_FLOW_CELL} suppressed.")
        else:
            st.info("Insufficient switching data for flow matrix.")

    # ── Context footer ───────────────────────────────────────────
    render_context_footer(
        screen_name="switching_market",
        product=product,
        period=period,
        sample_n=n_mkt,
    )


# ---------------------------------------------------------------------------
# Insurer view
# ---------------------------------------------------------------------------

def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer-level switching and flows deep-dive."""
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

    # ── Calculate all metrics upfront (needed for narrative) ─────
    ins_retention = calc_retention_rate(df_ins)
    mkt_retention = calc_retention_rate(df_mkt)
    ins_switching = calc_switching_rate(df_ins)
    mkt_switching = calc_switching_rate(df_mkt)

    nf = calc_net_flow(df_mkt, insurer, base=n_ins)
    net = nf["net"]
    net_sign = "+" if net > 0 else ""

    sources = calc_top_sources(df_mkt, insurer, 5)
    destinations = calc_top_destinations(df_mkt, insurer, 5)

    # ── Context bar ──────────────────────────────────────────────
    render_context_bar(
        "Switching & Flows",
        insurer=insurer,
        product=product,
        period=period,
        n_insurer=n_ins,
        n_market=n_mkt,
    )

    # ── Suppression check ────────────────────────────────────────
    if n_ins < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # ── AI Narrative (top of screen) ─────────────────────────────
    sources_list = [str(s) for s in sources.index[:3]] if len(sources) > 0 else []
    dest_list = [str(d) for d in destinations.index[:3]] if len(destinations) > 0 else []
    narrative = generate_screen_narrative("switching", {
        "insurer": insurer,
        "product": product,
        "retention_rate": ins_retention or 0,
        "mkt_retention_rate": mkt_retention or 0,
        "net_flow": net,
        "gained": nf["gained"],
        "lost": nf["lost"],
        "top_sources": ", ".join(sources_list) or "N/A",
        "top_destinations": ", ".join(dest_list) or "N/A",
    })
    render_narrative_compact(narrative, "switching")

    # ── KPI row ──────────────────────────────────────────────────
    retention_gap = ((ins_retention or 0) - (mkt_retention or 0)) * 100
    retention_trend = "up" if retention_gap > 0 else "down" if retention_gap < 0 else "flat"
    retention_sign = "+" if retention_gap > 0 else ""

    switching_gap = ((ins_switching or 0) - (mkt_switching or 0)) * 100
    # Lower switching is better, so invert the signal
    switching_trend = "up" if switching_gap < 0 else "down" if switching_gap > 0 else "flat"

    net_trend = "up" if net > 0 else "down" if net < 0 else "flat"
    net_pct_display = format_net_flow_pct(nf.get("net_pct"))

    decision_kpi_row([
        {
            "title": "Retention Rate",
            "value": fmt_pct(ins_retention),
            "change": f"{retention_sign}{retention_gap:.1f}pp vs market",
            "trend": retention_trend,
            "sample_n": n_ins,
            "colour": CI_GREEN if retention_gap >= 0 else CI_RED,
        },
        {
            "title": "Switching Rate",
            "value": fmt_pct(ins_switching),
            "change": f"{'+' if switching_gap < 0 else ''}{switching_gap:.1f}pp vs market",
            "trend": switching_trend,
            "sample_n": n_ins,
            "colour": kpi_vs_market_colour(ins_switching, mkt_switching, lower_is_better=True),
        },
        {
            "title": "Net Flow",
            "value": net_pct_display,
            "change": f"of renewal base ({net_sign}{net:,} respondents)",
            "trend": net_trend,
            "sample_n": n_ins,
            "colour": CI_GREEN if net > 0 else CI_RED if net < 0 else CI_GREY,
        },
    ])

    # ── 70 / 30 split ───────────────────────────────────────────
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Flow Intelligence: Over/Under Index
        result = calc_flow_index(df_mkt, insurer)

        df_loss = result["loss_index"]
        if not df_loss.empty:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
                f'color:{CI_RED}; margin-bottom:6px;">Losing Disproportionately To</div>',
                unsafe_allow_html=True,
            )
            _render_index_chart(df_loss, direction="loss")
            st.caption(
                f"Index > 100 = losing disproportionately. "
                f"Based on {result['insurer_lost']:,} lost."
            )

        df_gain = result["gain_index"]
        if not df_gain.empty:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
                f'color:{CI_GREEN}; margin:12px 0 6px 0;">Winning Disproportionately From</div>',
                unsafe_allow_html=True,
            )
            _render_index_chart(df_gain, direction="gain")
            st.caption(
                f"Index > 100 = winning disproportionately. "
                f"Based on {result['insurer_gained']:,} gained."
            )

        if df_loss.empty and df_gain.empty:
            st.info("Insufficient switching data for flow index analysis.")

    with col_secondary:
        # Customer Flows: Sources and Destinations
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREEN}; margin-bottom:6px;">Winning From</div>',
            unsafe_allow_html=True,
        )
        if len(sources) > 0:
            total_gained = int(sources.sum())
            for competitor, count in sources.items():
                if count < MIN_BASE_FLOW_CELL:
                    continue
                pct_str = format_flow_pct(int(count), total_gained) or "—"
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'<span style="color:{CI_GREY};">{competitor}</span>'
                    f'<span style="float:right; font-weight:700; color:{CI_GREEN};">{pct_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No source data available.")

        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_RED}; margin:12px 0 6px 0;">Losing To</div>',
            unsafe_allow_html=True,
        )
        if len(destinations) > 0:
            total_lost = int(destinations.sum())
            for competitor, count in destinations.items():
                if count < MIN_BASE_FLOW_CELL:
                    continue
                pct_str = format_flow_pct(int(count), total_lost) or "—"
                # Strip the "+" prefix and prepend "−" (minus sign) for lost flows
                display_str = "\u2212" + pct_str.lstrip("+")
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'<span style="color:{CI_GREY};">{competitor}</span>'
                    f'<span style="float:right; font-weight:700; color:{CI_RED};">{display_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No destination data available.")

        # Departed Sentiment — insurer vs market, rendered as decision_kpi cards
        sentiment = calc_departed_sentiment(df_mkt, insurer)
        mkt_sentiment = calc_market_departed_sentiment(df_mkt)
        if sentiment and sentiment.get("n", 0) >= MIN_BASE_REASON:
            ins_sat = sentiment.get("mean_q40a")
            ins_nps = sentiment.get("nps")
            mkt_sat = mkt_sentiment.get("mean_q40a") if mkt_sentiment else None
            mkt_nps = mkt_sentiment.get("nps") if mkt_sentiment else None

            st.markdown(
                f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
                f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">Departed Sentiment</div>',
                unsafe_allow_html=True,
            )

            sat_change = (
                f"Market: {mkt_sat:.2f}/5" if mkt_sat is not None else "Market: \u2014"
            )
            sat_trend = (
                "up" if (ins_sat is not None and mkt_sat is not None and ins_sat > mkt_sat)
                else "down" if (ins_sat is not None and mkt_sat is not None and ins_sat < mkt_sat)
                else "flat"
            )

            nps_change = (
                f"Market: {mkt_nps:+.0f}" if mkt_nps is not None else "Market: \u2014"
            )
            nps_trend = (
                "up" if (ins_nps is not None and mkt_nps is not None and ins_nps > mkt_nps)
                else "down" if (ins_nps is not None and mkt_nps is not None and ins_nps < mkt_nps)
                else "flat"
            )

            sentiment_cards = []
            if ins_sat is not None:
                sentiment_cards.append({
                    "title": "Satisfaction",
                    "value": f"{ins_sat:.2f}/5",
                    "change": sat_change,
                    "trend": sat_trend,
                    "sample_n": sentiment["n"],
                    "colour": kpi_vs_market_colour(ins_sat, mkt_sat),
                })
            if ins_nps is not None:
                sentiment_cards.append({
                    "title": "NPS (Departed)",
                    "value": f"{ins_nps:+.0f}",
                    "change": nps_change,
                    "trend": nps_trend,
                    "sample_n": sentiment["n"],
                    "colour": kpi_vs_market_colour(ins_nps, mkt_nps),
                })
            if sentiment_cards:
                decision_kpi_row(sentiment_cards)

        # Cross-screen links
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">Explore</div>',
            unsafe_allow_html=True,
        )
        if st.button("Reasons & Drivers", key="switching_to_reasons"):
            from lib.state import navigate_to
            navigate_to("reasons")
        if st.button("Shopping Behaviour", key="switching_to_shopping"):
            from lib.state import navigate_to
            navigate_to("shopping")
        if st.button("Compare Insurers", key="switching_to_comparison"):
            from lib.state import navigate_to
            navigate_to("comparison")

    # ── Context footer ───────────────────────────────────────────
    render_context_footer(
        screen_name="switching",
        product=product,
        period=period,
        sample_n=n_ins,
    )


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _render_index_chart(df_index: pd.DataFrame, direction: str = "loss"):
    """Render a horizontal bar chart for flow over/under index."""
    if df_index.empty:
        return

    n = len(df_index)

    colours = [
        get_index_bar_colour(row["index"], direction)
        for _, row in df_index.iterrows()
    ]

    fig = go.Figure(go.Bar(
        x=df_index["index"],
        y=df_index["competitor"],
        orientation="h",
        marker_color=colours,
        text=[f"{v:.0f}" for v in df_index["index"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Index: %{x:.0f}<br>"
            "Your share: %{customdata[0]:.1%}<br>"
            "Market share: %{customdata[1]:.1%}<br>"
            "Count: %{customdata[2]:,}"
            "<extra></extra>"
        ),
        customdata=df_index[["insurer_share", "market_share", "raw_count"]].values,
    ))

    fig.add_vline(
        x=100,
        line_dash="dash",
        line_color=CI_GREY,
        line_width=2,
    )

    fig.update_layout(
        height=max(220, n * 28),
        xaxis=dict(title="Index (100 = expected rate)", gridcolor=CI_LIGHT_GREY),
        yaxis=dict(title="", autorange="reversed"),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=80, t=10, b=30),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

"""
Screen 5: Switching & Flows.

Market View: Switching rate trend, flow matrix overview, top movers.
Insurer View: Net flow, top sources/destinations, flow index, departed sentiment.
Combines content from pages/2 (flows section), pages/10 (flow intelligence).
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
)
from lib.analytics.rates import (
    calc_retention_rate,
    calc_shopping_rate,
    calc_switching_rate,
)
from lib.chart_export import render_suppression_html
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_panel
from lib.config import (
    CI_BLUE,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    CI_VIOLET,
    MARKET_COLOUR,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, section_divider, period_label, card_html, FONT
from lib.state import format_year_month, get_ss_data


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


def _render_market_view(df_motor, df_mkt, filters, period, n_mkt):
    """Market-level switching and flows overview."""
    st.subheader("Switching & Flows: Market View")

    # --- KPI cards ---
    switching_rate = calc_switching_rate(df_mkt)
    retention_rate = calc_retention_rate(df_mkt)
    shopping_rate = calc_shopping_rate(df_mkt)

    col1, col2, col3 = st.columns(3)
    with col1:
        kpi_card(
            "Market Switching Rate",
            fmt_pct(switching_rate),
            f"n={n_mkt:,}",
            CI_RED,
        )
    with col2:
        kpi_card(
            "Market Retention Rate",
            fmt_pct(retention_rate),
            f"n={n_mkt:,}",
            CI_GREEN,
        )
    with col3:
        kpi_card(
            "Market Shopping Rate",
            fmt_pct(shopping_rate),
            f"n={n_mkt:,}",
            CI_MAGENTA,
        )

    # --- Switching rate by month ---
    section_divider("Switching Rate Trend")

    if "RenewalYearMonth" in df_mkt.columns:
        months = sorted(df_mkt["RenewalYearMonth"].dropna().unique().astype(int))
        trend_rows = []
        for m in months:
            df_month = df_mkt[df_mkt["RenewalYearMonth"] == m]
            sw = calc_switching_rate(df_month)
            if sw is not None:
                trend_rows.append({
                    "month": m,
                    "label": format_year_month(m),
                    "switching_rate": sw,
                    "n": len(df_month),
                })

        if trend_rows:
            trend_df = pd.DataFrame(trend_rows)
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

    # --- Flow matrix summary ---
    section_divider("Flow Matrix (Top Movers)")

    flow_mat = calc_flow_matrix(df_mkt)
    if not flow_mat.empty:
        # Show top 10 by total volume
        row_totals = flow_mat.sum(axis=1).sort_values(ascending=False)
        top_insurers = row_totals.head(10).index.tolist()

        display_mat = flow_mat.loc[
            flow_mat.index.isin(top_insurers),
            flow_mat.columns.isin(top_insurers),
        ]

        st.dataframe(
            display_mat.style.background_gradient(cmap="YlOrRd", axis=None).format("{:.0f}"),
            use_container_width=True,
        )
        st.caption(
            "Rows = previous insurer, Columns = current insurer. "
            f"Top 10 by volume. Cells < {MIN_BASE_FLOW_CELL} should be treated with caution."
        )
    else:
        st.info("Insufficient switching data for flow matrix.")

    # --- Footer ---
    st.markdown("---")
    st.caption(f"Switching & Flows | Market | {filters['product']} | {period} | n={n_mkt:,}")


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

    st.subheader(f"Switching & Flows: {insurer}")

    # Period banner
    st.markdown(
        f'<div style="background:{CI_LIGHT_GREY}; padding:10px 16px; border-radius:4px; '
        f'font-family:{FONT}; font-size:13px; color:{CI_GREY}; margin-bottom:16px;">'
        f"<b>{insurer}</b> &nbsp;|&nbsp; {product} &nbsp;|&nbsp; {period} "
        f"&nbsp;|&nbsp; Insurer n={n_ins:,} &nbsp;|&nbsp; Market n={n_mkt:,}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Suppression check
    if n_ins < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # --- KPI cards: retention, switching, net flow ---
    section_divider("Headline Metrics")

    ins_retention = calc_retention_rate(df_ins)
    mkt_retention = calc_retention_rate(df_mkt)
    ins_switching = calc_switching_rate(df_ins)
    mkt_switching = calc_switching_rate(df_mkt)

    nf = calc_net_flow(df_mkt, insurer, base=n_ins)
    net = nf["net"]
    net_colour = CI_GREEN if net > 0 else CI_RED if net < 0 else CI_GREY
    net_icon = "\u25B2" if net > 0 else "\u25BC" if net < 0 else "\u25C6"
    net_sign = "+" if net > 0 else ""

    col1, col2, col3 = st.columns(3)
    with col1:
        gap = ((ins_retention or 0) - (mkt_retention or 0)) * 100
        sign = "+" if gap > 0 else ""
        kpi_card(
            "Retention Rate",
            fmt_pct(ins_retention),
            f"Market: {fmt_pct(mkt_retention)} ({sign}{gap:.1f}pp)",
            CI_GREEN if gap >= 0 else CI_RED,
        )
    with col2:
        kpi_card(
            "Switching Rate",
            fmt_pct(ins_switching),
            f"Market: {fmt_pct(mkt_switching)}",
            CI_MAGENTA,
        )
    with col3:
        net_pct_str = ""
        if nf.get("net_pct") is not None:
            net_pct_str = f" ({net_sign}{nf['net_pct']:.1%})"
        kpi_card(
            "Net Flow",
            f"{net_icon} {net_sign}{net:,}{net_pct_str}",
            f"+{nf['gained']:,} gained, -{nf['lost']:,} lost",
            net_colour,
        )

    # --- Top Sources and Destinations ---
    section_divider("Customer Flows")

    sources = calc_top_sources(df_mkt, insurer, 5)
    destinations = calc_top_destinations(df_mkt, insurer, 5)

    col_src, col_dst = st.columns(2)

    with col_src:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; color:{CI_GREEN}; '
            f'margin-bottom:8px;">Winning From (Top Sources)</div>',
            unsafe_allow_html=True,
        )
        if len(sources) > 0:
            for competitor, count in sources.items():
                if count < MIN_BASE_FLOW_CELL:
                    continue
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:13px; padding:4px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'<span style="color:{CI_GREY};">{competitor}</span>'
                    f'<span style="float:right; font-weight:bold; color:{CI_GREEN};">+{count}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No source data available.")

    with col_dst:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; color:{CI_RED}; '
            f'margin-bottom:8px;">Losing To (Top Destinations)</div>',
            unsafe_allow_html=True,
        )
        if len(destinations) > 0:
            for competitor, count in destinations.items():
                if count < MIN_BASE_FLOW_CELL:
                    continue
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:13px; padding:4px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'<span style="color:{CI_GREY};">{competitor}</span>'
                    f'<span style="float:right; font-weight:bold; color:{CI_RED};">\u2212{count}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No destination data available.")

    # --- Flow Index (Over/Under) ---
    section_divider("Flow Intelligence: Over/Under Index")

    result = calc_flow_index(df_mkt, insurer)

    # Loss index
    df_loss = result["loss_index"]
    if not df_loss.empty:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; '
            f'color:{CI_RED}; margin-bottom:8px;">Where Are You Losing Disproportionately?</div>',
            unsafe_allow_html=True,
        )
        _render_index_chart(df_loss, direction="loss")
        st.caption(
            f"Index above 100 = losing disproportionately to this competitor. "
            f"Based on {result['insurer_lost']:,} customers lost."
        )

    # Gain index
    df_gain = result["gain_index"]
    if not df_gain.empty:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; '
            f'color:{CI_GREEN}; margin:16px 0 8px 0;">Where Are You Winning Disproportionately?</div>',
            unsafe_allow_html=True,
        )
        _render_index_chart(df_gain, direction="gain")
        st.caption(
            f"Index above 100 = winning disproportionately from this competitor. "
            f"Based on {result['insurer_gained']:,} customers gained."
        )

    if df_loss.empty and df_gain.empty:
        st.info("Insufficient switching data for flow index analysis.")

    # --- Departed Sentiment ---
    section_divider("Departed Customer Sentiment (Q40a / Q40b)")

    sentiment = calc_departed_sentiment(df_mkt, insurer)

    if sentiment and sentiment.get("n", 0) >= MIN_BASE_REASON:
        # Market-level departed sentiment
        all_switchers = df_mkt[df_mkt["IsSwitcher"]] if "IsSwitcher" in df_mkt.columns else pd.DataFrame()
        mkt_sat = None
        mkt_nps = None
        if len(all_switchers) >= MIN_BASE_REASON:
            if "Q40a" in all_switchers.columns:
                mkt_sat = all_switchers["Q40a"].mean()
            if "Q40b" in all_switchers.columns:
                nps_vals = pd.to_numeric(all_switchers["Q40b"], errors="coerce")
                promoters = (nps_vals >= 9).sum()
                detractors = (nps_vals <= 6).sum()
                mkt_nps = 100 * (promoters - detractors) / len(all_switchers)

        ins_sat = sentiment.get("mean_q40a")
        ins_nps = sentiment.get("nps")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            kpi_card(
                f"{insurer} Satisfaction",
                f"{ins_sat:.2f}" if ins_sat is not None else "\u2014",
                "Q40a mean (1-5)",
                CI_MAGENTA,
            )
        with col2:
            kpi_card(
                "Market Satisfaction",
                f"{mkt_sat:.2f}" if mkt_sat is not None else "\u2014",
                "Q40a mean (1-5)",
                MARKET_COLOUR,
            )
        with col3:
            nps_colour = CI_GREEN if ins_nps and ins_nps > 0 else CI_RED if ins_nps and ins_nps < 0 else CI_GREY
            kpi_card(
                f"{insurer} NPS",
                f"{ins_nps:+.0f}" if ins_nps is not None else "\u2014",
                "Q40b (0-10 scale)",
                nps_colour,
            )
        with col4:
            mkt_nps_colour = CI_GREEN if mkt_nps and mkt_nps > 0 else CI_RED if mkt_nps and mkt_nps < 0 else CI_GREY
            kpi_card(
                "Market NPS",
                f"{mkt_nps:+.0f}" if mkt_nps is not None else "\u2014",
                "Q40b (0-10 scale)",
                mkt_nps_colour,
            )

        st.caption(f"Base: {sentiment['n']:,} switchers from {insurer}")
    else:
        switcher_n = sentiment["n"] if sentiment else 0
        st.markdown(
            render_suppression_html(f"{insurer} (Departed Sentiment)", switcher_n, MIN_BASE_REASON),
            unsafe_allow_html=True,
        )

    # --- AI Narrative ---
    section_divider("AI Narrative")

    sources_list = [str(s) for s in sources.index[:3]] if len(sources) > 0 else []
    dest_list = [str(d) for d in destinations.index[:3]] if len(destinations) > 0 else []
    narrative = generate_screen_narrative("switching", {
        "insurer": insurer,
        "product": filters["product"],
        "retention_rate": ins_retention or 0,
        "mkt_retention_rate": mkt_retention or 0,
        "net_flow": net,
        "gained": nf["gained"],
        "lost": nf["lost"],
        "top_sources": ", ".join(sources_list) or "N/A",
        "top_destinations": ", ".join(dest_list) or "N/A",
    })
    render_narrative_panel(narrative, "switching")

    # --- Cross-screen links ---
    col_link1, col_link2, col_link3 = st.columns(3)
    with col_link1:
        if st.button("View Reasons & Drivers", key="switching_to_reasons"):
            from lib.state import navigate_to
            navigate_to("reasons")
    with col_link2:
        if st.button("View Shopping Behaviour", key="switching_to_shopping"):
            from lib.state import navigate_to
            navigate_to("shopping")
    with col_link3:
        if st.button("Compare Insurers", key="switching_to_comparison"):
            from lib.state import navigate_to
            navigate_to("comparison")

    # --- Footer ---
    st.markdown("---")
    st.caption(
        f"Switching & Flows | {insurer} | {filters['product']} | {period} | "
        f"Insurer n={n_ins:,} | Market n={n_mkt:,}"
    )


def _render_index_chart(df_index: pd.DataFrame, direction: str = "loss"):
    """Render a horizontal bar chart for flow over/under index."""
    if df_index.empty:
        return

    n = len(df_index)

    if direction == "loss":
        colours = [
            CI_RED if row["index"] > 120
            else CI_GREEN if row["index"] < 80
            else CI_BLUE
            for _, row in df_index.iterrows()
        ]
    else:
        colours = [
            CI_GREEN if row["index"] > 120
            else CI_RED if row["index"] < 80
            else CI_BLUE
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
        line_dash="dot",
        line_color=CI_MAGENTA,
        annotation_text="Market avg (100)",
        annotation_position="top right",
        annotation_font_color=CI_MAGENTA,
    )

    fig.update_layout(
        height=max(250, n * 30),
        xaxis=dict(title="Index (100 = market average)", gridcolor=CI_LIGHT_GREY),
        yaxis=dict(title="", autorange="reversed"),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=80, t=20, b=40),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

"""
Screen 4: Channels & PCWs.

Market View: Shopping channels (Q9b), PCW usage (Q11), PCW NPS.
Insurer View: Insurer vs market channel usage, quote reach.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.channels import (
    calc_channel_usage,
    calc_pcw_usage,
    calc_pcw_nps,
    calc_quote_buy_mismatch,
    calc_quote_reach,
)
from lib.analytics.demographics import apply_filters
from lib.chart_export import apply_export_metadata, render_suppression_html
from lib.components.kpi_cards import kpi_card
from lib.components.paired_bars import paired_bar_chart
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
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT
from lib.question_ref import get_question_text
from lib.state import get_ss_data


def render(filters: dict):
    """Render the Channels & PCWs screen."""
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
    """Market-level channel and PCW overview."""
    st.subheader("Channels & PCWs: Market View")

    n_shoppers = int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0

    # --- Shopping Channels (Q9b) ---
    section_divider("Shopping Channels (Q9b)")
    st.caption(get_question_text("Q9b"))
    st.caption("Multi-select: totals exceed 100%.")

    ch = calc_channel_usage(df_mkt)
    if ch is not None and len(ch) > 0:
        ch_sorted = ch.sort_values(ascending=True)
        fig = go.Figure(go.Bar(
            x=ch_sorted.values,
            y=ch_sorted.index,
            orientation="h",
            marker_color=CI_GREEN,
            text=[f"{v:.0%}" for v in ch_sorted.values],
            textposition="outside",
        ))
        fig.update_layout(
            xaxis_tickformat=".0%",
            height=max(250, len(ch) * 35 + 80),
            margin=dict(l=10, r=50, t=10, b=40),
            font=dict(family=FONT, size=11, color=CI_GREY),
            plot_bgcolor=CI_WHITE,
            paper_bgcolor=CI_WHITE,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No channel data available.")

    # --- PCW Usage (Q11) ---
    section_divider("PCW Market Share (Q11)")
    st.caption(get_question_text("Q11"))

    pcw = calc_pcw_usage(df_mkt)
    if pcw is not None and len(pcw) > 0:
        col_pie, col_table = st.columns([2, 1])
        with col_pie:
            fig_pcw = go.Figure(go.Pie(
                labels=pcw.index,
                values=pcw.values,
                hole=0.4,
                textinfo="label+percent",
                marker=dict(line=dict(color="white", width=2)),
            ))
            fig_pcw.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=20, b=40),
                font=dict(family=FONT),
            )
            st.plotly_chart(fig_pcw, use_container_width=True)

        with col_table:
            pcw_df = pd.DataFrame({"PCW": pcw.index, "Usage": [f"{v:.0%}" for v in pcw.values]})
            st.dataframe(pcw_df, use_container_width=True, hide_index=True)
    else:
        st.info("No PCW data available.")

    # --- Quote/Buy Mismatch ---
    section_divider("Quote vs Buy Mismatch")
    mismatch = calc_quote_buy_mismatch(df_mkt)
    if mismatch is not None:
        kpi_card(
            "Quote/Buy Mismatch Rate",
            fmt_pct(mismatch),
            "Shoppers who quoted via one channel but bought via another",
            CI_RED,
        )
    else:
        st.info("No mismatch data available.")

    # Footer
    st.markdown("---")
    st.caption(
        f"Channels & PCWs | Market | {filters['product']} | {period} | "
        f"n={n_mkt:,} | Shoppers: {n_shoppers:,}"
    )


def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer-level channel analysis."""
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

    st.subheader(f"Channels & PCWs: {insurer}")

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

    # --- Channel usage: insurer vs market ---
    section_divider("Shopping Channels: Insurer vs Market (Q9b)")

    ch_ins = calc_channel_usage(df_mkt, insurer)
    ch_mkt = calc_channel_usage(df_mkt)

    if ch_ins is not None and ch_mkt is not None:
        # Align channels
        all_channels = sorted(set(ch_ins.index) | set(ch_mkt.index))
        labels = all_channels
        ins_vals = [ch_ins.get(c, 0) for c in all_channels]
        mkt_vals = [ch_mkt.get(c, 0) for c in all_channels]

        paired_bar_chart(
            labels, ins_vals, mkt_vals,
            insurer_label=insurer, market_label="Market",
            title="Channel Usage Among Shoppers",
            insurer_colour=CI_VIOLET,
        )
    else:
        st.info("Insufficient channel data for comparison.")

    # --- PCW usage: insurer vs market ---
    section_divider("PCW Usage: Insurer vs Market (Q11)")

    pcw_ins = calc_pcw_usage(df_mkt, insurer)
    pcw_mkt = calc_pcw_usage(df_mkt)

    if pcw_ins is not None and pcw_mkt is not None:
        all_pcws = sorted(set(pcw_ins.index) | set(pcw_mkt.index))
        labels = all_pcws
        ins_vals = [pcw_ins.get(p, 0) for p in all_pcws]
        mkt_vals = [pcw_mkt.get(p, 0) for p in all_pcws]

        paired_bar_chart(
            labels, ins_vals, mkt_vals,
            insurer_label=insurer, market_label="Market",
            title="PCW Usage Among PCW Shoppers",
            insurer_colour=CI_VIOLET,
        )
    else:
        st.info("Insufficient PCW data for comparison.")

    # --- Quote reach ---
    section_divider("Quote Reach (Q13b)")

    quote_reach = calc_quote_reach(df_mkt, insurer)
    n_shoppers = int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0
    reach_pct = quote_reach / n_shoppers if n_shoppers > 0 else 0

    col1, col2 = st.columns(2)
    with col1:
        kpi_card("Quote Reach", f"{quote_reach:,}", "Shoppers who got a quote from this insurer", CI_MAGENTA)
    with col2:
        kpi_card("Reach %", fmt_pct(reach_pct), f"Of {n_shoppers:,} total shoppers", CI_MAGENTA)

    # Footer
    st.markdown("---")
    st.caption(
        f"Channels & PCWs | {insurer} | {filters['product']} | {period} | "
        f"Insurer n={n_ins:,} | Market n={n_mkt:,}"
    )

"""
Screen 4: Channels & PCWs.

Market View: Shopping channels (Q9b), PCW usage (Q11), PCW NPS.
Insurer View: Insurer vs market channel usage, quote reach.

Layout: Decision Screen pattern (context bar, narrative, KPIs, 70/30 split, footer).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.channels import (
    calc_channel_usage,
    calc_pcw_usage,
    calc_pcw_nps,
    calc_quote_buy_mismatch,
    calc_quote_reach,
)
from lib.analytics.demographics import apply_filters
from lib.chart_export import render_suppression_html
from lib.components.context_bar import render_context_bar
from lib.components.context_footer import render_context_footer
from lib.components.decision_kpi import decision_kpi_row
from lib.components.narrative_panel import render_narrative_compact
from lib.components.paired_bars import paired_bar_chart
from lib.components.question_info import render_question_info
from lib.config import (
    CI_BLUE,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    CI_VIOLET,
    FONT,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, period_label
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


# ---------------------------------------------------------------------------
# Market view
# ---------------------------------------------------------------------------

def _render_market_view(df_mkt, filters, period, n_mkt):
    """Market-level channel and PCW overview."""
    product = filters["product"]
    n_shoppers = int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0

    # -- Context bar --
    render_context_bar(
        "Channels & PCWs",
        product=product,
        period=period,
        n_market=n_mkt,
    )

    # -- KPI row --
    mismatch = calc_quote_buy_mismatch(df_mkt)
    shopping_rate = n_shoppers / n_mkt if n_mkt else None
    decision_kpi_row([
        {
            "title": "Shopping Rate",
            "value": fmt_pct(shopping_rate),
            "change": "of market respondents shopped",
            "sample_n": n_shoppers,
            "colour": CI_MAGENTA,
        },
        {
            "title": "Quote/Buy Mismatch",
            "value": fmt_pct(mismatch) if mismatch is not None else "--",
            "sample_n": n_shoppers,
            "colour": CI_RED,
        },
    ])

    # -- 70 / 30 split --
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Shopping Channels (Q9b)
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
            f'color:{CI_GREEN}; margin-bottom:6px;">Shopping Channels (Q9b)</div>',
            unsafe_allow_html=True,
        )
        render_question_info("Q9a")

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

        # PCW Usage (Q11)
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
            f'color:{CI_MAGENTA}; margin:16px 0 6px 0;">PCW Market Share (Q11)</div>',
            unsafe_allow_html=True,
        )

        pcw = calc_pcw_usage(df_mkt)
        if pcw is not None and len(pcw) > 0:
            fig_pcw = go.Figure(go.Pie(
                labels=pcw.index,
                values=pcw.values,
                hole=0.4,
                textinfo="label+percent",
                marker=dict(line=dict(color="white", width=2)),
            ))
            fig_pcw.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=20, b=40),
                font=dict(family=FONT),
            )
            st.plotly_chart(fig_pcw, use_container_width=True)
        else:
            st.info("No PCW data available.")

    with col_secondary:
        # PCW table
        if pcw is not None and len(pcw) > 0:
            st.markdown(
                f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
                f'letter-spacing:0.8px; color:{CI_GREY}; margin-bottom:8px;">PCW Usage</div>',
                unsafe_allow_html=True,
            )
            pcw_df = pd.DataFrame({"PCW": pcw.index, "Usage": [f"{v:.0%}" for v in pcw.values]})
            st.dataframe(pcw_df, use_container_width=True, hide_index=True)

    # -- Context footer --
    render_context_footer(
        screen_name="channels_market",
        product=product,
        period=period,
        sample_n=n_mkt,
    )


# ---------------------------------------------------------------------------
# Insurer view
# ---------------------------------------------------------------------------

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

    # -- Calculate metrics upfront (needed for narrative) --
    ch_ins = calc_channel_usage(df_mkt, insurer)
    ch_mkt = calc_channel_usage(df_mkt)
    pcw_ins = calc_pcw_usage(df_mkt, insurer)
    pcw_mkt = calc_pcw_usage(df_mkt)
    n_shoppers = int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0
    quote_reach = calc_quote_reach(df_mkt, insurer)
    reach_pct = quote_reach / n_shoppers if n_shoppers > 0 else 0

    # -- Context bar --
    render_context_bar(
        "Channels & PCWs",
        insurer=insurer,
        product=product,
        period=period,
        n_insurer=n_ins,
        n_market=n_mkt,
    )

    # -- Suppression check --
    if n_ins < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # -- AI Narrative (top of screen) --
    top_ch = ch_ins.idxmax() if ch_ins is not None and len(ch_ins) > 0 else "N/A"
    pcw_rate = f"{pcw_ins.sum():.0%}" if pcw_ins is not None else "N/A"
    narrative = generate_screen_narrative("channels", {
        "insurer": insurer,
        "product": product,
        "top_channel": top_ch,
        "pcw_usage_rate": pcw_rate,
        "quote_reach": quote_reach,
    })
    render_narrative_compact(narrative, "channels")

    # -- KPI row --
    decision_kpi_row([
        {
            "title": "Quote Reach",
            "value": fmt_pct(reach_pct),
            "change": "of active shoppers received a quote",
            "trend": "up" if reach_pct > 0.1 else "flat",
            "sample_n": n_ins,
            "colour": CI_MAGENTA,
        },
        {
            "title": "Top Channel",
            "value": top_ch,
            "sample_n": n_ins,
            "colour": CI_VIOLET,
        },
    ])

    # -- 70 / 30 split --
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        render_question_info("Q9a")
        # Channel usage: insurer vs market (Q9b)
        if ch_ins is not None and ch_mkt is not None:
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

        # PCW usage: insurer vs market (Q11)
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

    with col_secondary:
        # Quote reach detail
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin-bottom:8px;">Quote Reach (Q13b)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; padding:4px 0; '
            f'border-bottom:1px solid {CI_LIGHT_GREY};">'
            f'<span style="color:{CI_GREY};">Quote reach</span>'
            f'<span style="float:right; font-weight:700; color:{CI_MAGENTA};" '
            f'title="n={quote_reach:,} shoppers quoted">{fmt_pct(reach_pct)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; padding:4px 0; '
            f'border-bottom:1px solid {CI_LIGHT_GREY};">'
            f'<span style="color:{CI_GREY};">vs market shoppers</span>'
            f'<span style="float:right; font-weight:700; color:{CI_MAGENTA};">{fmt_pct(reach_pct)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Cross-screen links
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">Explore</div>',
            unsafe_allow_html=True,
        )
        if st.button("Shopping Behaviour", key="channels_to_shopping"):
            from lib.state import navigate_to
            navigate_to("shopping")
        if st.button("Pre-Renewal Context", key="channels_to_prerenewal"):
            from lib.state import navigate_to
            navigate_to("pre_renewal")
        if st.button("Compare Insurers", key="channels_to_comparison"):
            from lib.state import navigate_to
            navigate_to("comparison")

    # -- Context footer --
    render_context_footer(
        screen_name="channels",
        product=product,
        period=period,
        sample_n=n_ins,
    )

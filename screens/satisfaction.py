"""
Screen 7: Satisfaction & Loyalty.

Market View: Overall satisfaction (Q47), NPS (Q48), satisfaction-retention matrix.
Insurer View: Insurer vs market satisfaction, NPS, brand perception (Q46),
              previous insurer sentiment.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.satisfaction import (
    calc_overall_satisfaction,
    calc_nps,
    calc_brand_perception,
    calc_satisfaction_retention_matrix,
    calc_previous_insurer_satisfaction,
)
from lib.chart_export import render_suppression_html
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_panel
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_VIOLET,
    CI_WHITE,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT
from lib.state import get_ss_data


def render(filters: dict):
    """Render the Satisfaction & Loyalty screen."""
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
    """Market-level satisfaction overview."""
    st.subheader("Satisfaction & Loyalty: Market View")

    # --- KPIs ---
    sat = calc_overall_satisfaction(df_mkt, "Q47")
    nps = calc_nps(df_mkt, "Q48")

    col1, col2, col3 = st.columns(3)
    with col1:
        kpi_card(
            "Market Satisfaction (Q47)",
            f"{sat['mean']:.2f}" if sat else "\u2014",
            f"n={sat['n']:,}" if sat else "No data",
            CI_MAGENTA,
        )
    with col2:
        nps_colour = CI_GREEN if nps and nps["nps"] > 0 else CI_RED if nps and nps["nps"] < 0 else CI_GREY
        kpi_card(
            "Market NPS (Q48)",
            f"{nps['nps']:+.0f}" if nps else "\u2014",
            f"n={nps['n']:,}" if nps else "No data",
            nps_colour,
        )
    with col3:
        if nps:
            kpi_card(
                "NPS Breakdown",
                f"{nps['promoters_pct']:.0%} / {nps['passives_pct']:.0%} / {nps['detractors_pct']:.0%}",
                "Promoters / Passives / Detractors",
                CI_GREY,
            )

    # --- Satisfaction Distribution ---
    if sat and sat.get("distribution"):
        section_divider("Satisfaction Distribution (Q47)")
        dist = sat["distribution"]
        scores = sorted(dist.keys())
        fig = go.Figure(go.Bar(
            x=[str(s) for s in scores],
            y=[dist[s] for s in scores],
            marker_color=CI_MAGENTA,
            text=[f"{dist[s]:.0%}" for s in scores],
            textposition="outside",
        ))
        fig.update_layout(
            height=250,
            yaxis=dict(tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            xaxis=dict(title="Satisfaction Score (1-5)"),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Satisfaction-Retention Matrix ---
    section_divider("Satisfaction vs Retention")

    sat_ret = calc_satisfaction_retention_matrix(df_mkt)
    if sat_ret is not None and not sat_ret.empty:
        fig = go.Figure(go.Bar(
            x=sat_ret["satisfaction_band"],
            y=sat_ret["retained_pct"],
            marker_color=[CI_RED, CI_GREY, CI_GREEN, CI_GREEN],
            text=[f"{r:.0%}" for r in sat_ret["retained_pct"]],
            textposition="outside",
            hovertemplate="Band: %{x}<br>Retention: %{y:.1%}<br>n=%{customdata:,}<extra></extra>",
            customdata=sat_ret["n"],
        ))
        fig.update_layout(
            height=300,
            yaxis=dict(title="Retention Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
            xaxis=dict(title="Satisfaction Band"),
            plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
            font=dict(family=FONT, size=11, color=CI_GREY),
            margin=dict(l=10, r=20, t=10, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Higher satisfaction correlates with higher retention. Bands based on Q47 scores.")
    else:
        st.info("Insufficient data for satisfaction-retention matrix.")

    st.markdown("---")
    st.caption(f"Satisfaction & Loyalty | Market | {filters['product']} | {period} | n={n_mkt:,}")


def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer-level satisfaction analysis."""
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

    st.subheader(f"Satisfaction & Loyalty: {insurer}")

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

    # --- KPIs: insurer vs market ---
    section_divider("Satisfaction & NPS")

    ins_sat = calc_overall_satisfaction(df_ins, "Q47")
    mkt_sat = calc_overall_satisfaction(df_mkt, "Q47")
    ins_nps = calc_nps(df_ins, "Q48")
    mkt_nps = calc_nps(df_mkt, "Q48")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card(
            f"{insurer} Satisfaction",
            f"{ins_sat['mean']:.2f}" if ins_sat else "\u2014",
            "Q47 mean (1-5)",
            CI_MAGENTA,
        )
    with col2:
        kpi_card(
            "Market Satisfaction",
            f"{mkt_sat['mean']:.2f}" if mkt_sat else "\u2014",
            "Q47 mean (1-5)",
            MARKET_COLOUR,
        )
    with col3:
        nps_val = ins_nps["nps"] if ins_nps else None
        nps_colour = CI_GREEN if nps_val and nps_val > 0 else CI_RED if nps_val and nps_val < 0 else CI_GREY
        kpi_card(
            f"{insurer} NPS",
            f"{nps_val:+.0f}" if nps_val is not None else "\u2014",
            "Q48 (0-10)",
            nps_colour,
        )
    with col4:
        mkt_nps_val = mkt_nps["nps"] if mkt_nps else None
        mkt_nps_colour = CI_GREEN if mkt_nps_val and mkt_nps_val > 0 else CI_RED if mkt_nps_val and mkt_nps_val < 0 else CI_GREY
        kpi_card(
            "Market NPS",
            f"{mkt_nps_val:+.0f}" if mkt_nps_val is not None else "\u2014",
            "Q48 (0-10)",
            mkt_nps_colour,
        )

    # --- Brand Perception (Q46) ---
    section_divider("Brand Perception (Q46)")

    ins_perception = calc_brand_perception(df_mkt, insurer)
    mkt_perception = calc_brand_perception(df_mkt)

    if ins_perception is not None and mkt_perception is not None:
        merged = ins_perception.merge(
            mkt_perception, on="subject", suffixes=("_ins", "_mkt")
        )
        if not merged.empty:
            merged = merged.sort_values("mean_score_ins", ascending=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=merged["subject"],
                x=merged["mean_score_mkt"],
                orientation="h",
                name="Market",
                marker_color=CI_GREY,
                opacity=0.5,
            ))
            fig.add_trace(go.Bar(
                y=merged["subject"],
                x=merged["mean_score_ins"],
                orientation="h",
                name=insurer,
                marker_color=CI_VIOLET,
            ))
            fig.update_layout(
                barmode="group",
                height=max(300, len(merged) * 35 + 80),
                xaxis=dict(title="Mean Score", gridcolor=CI_LIGHT_GREY),
                plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
                font=dict(family=FONT, size=11, color=CI_GREY),
                margin=dict(l=10, r=40, t=10, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1, xanchor="right"),
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No Q46 brand perception data available.")

    # --- Previous Insurer Satisfaction ---
    section_divider("Previous Insurer Satisfaction (Q40a / Q40b)")

    ins_prev = calc_previous_insurer_satisfaction(df_mkt, insurer)
    mkt_prev = calc_previous_insurer_satisfaction(df_mkt)

    if ins_prev and ins_prev.get("n", 0) >= MIN_BASE_REASON:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            kpi_card(
                f"Departed Satisfaction",
                f"{ins_prev.get('mean_q40a', 0):.2f}" if ins_prev.get("mean_q40a") else "\u2014",
                "Q40a (1-5)",
                CI_MAGENTA,
            )
        with col2:
            kpi_card(
                "Market Departed Sat.",
                f"{mkt_prev.get('mean_q40a', 0):.2f}" if mkt_prev and mkt_prev.get("mean_q40a") else "\u2014",
                "Q40a (1-5)",
                MARKET_COLOUR,
            )
        with col3:
            dep_nps = ins_prev.get("nps")
            dep_colour = CI_GREEN if dep_nps and dep_nps > 0 else CI_RED if dep_nps and dep_nps < 0 else CI_GREY
            kpi_card("Departed NPS", f"{dep_nps:+.0f}" if dep_nps is not None else "\u2014", "Q40b", dep_colour)
        with col4:
            kpi_card("Base", f"{ins_prev['n']:,}", f"Switchers from {insurer}", CI_GREY)
    else:
        n_dep = ins_prev["n"] if ins_prev else 0
        st.markdown(
            render_suppression_html(f"{insurer} (Departed Satisfaction)", n_dep, MIN_BASE_REASON),
            unsafe_allow_html=True,
        )

    # --- AI Narrative ---
    section_divider("AI Narrative")
    ins_sat_val = ins_sat["mean"] if ins_sat else 0
    mkt_sat_val = mkt_sat["mean"] if mkt_sat else 0
    ins_nps_val = ins_nps["nps"] if ins_nps else 0
    mkt_nps_val = mkt_nps["nps"] if mkt_nps else 0
    dep_sat_str = f"{ins_prev.get('mean_q40a', 0):.2f}" if ins_prev and ins_prev.get("mean_q40a") else "N/A"
    narrative = generate_screen_narrative("satisfaction", {
        "insurer": insurer,
        "product": filters["product"],
        "satisfaction": ins_sat_val,
        "mkt_satisfaction": mkt_sat_val,
        "nps": ins_nps_val,
        "mkt_nps": mkt_nps_val,
        "departed_sat": dep_sat_str,
    })
    render_narrative_panel(narrative, "satisfaction")

    # --- Cross-screen links ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Reasons & Drivers", key="satisfaction_to_reasons"):
            from lib.state import navigate_to
            navigate_to("reasons")
    with col2:
        if st.button("View Claims Intelligence", key="satisfaction_to_claims"):
            from lib.state import navigate_to
            navigate_to("claims")

    st.markdown("---")
    st.caption(
        f"Satisfaction & Loyalty | {insurer} | {filters['product']} | {period} | "
        f"Insurer n={n_ins:,} | Market n={n_mkt:,}"
    )

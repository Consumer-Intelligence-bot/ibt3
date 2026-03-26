"""
Screen 7: Satisfaction & Loyalty.

Market View: Overall satisfaction (Q47), NPS (Q48), satisfaction-retention matrix.
Insurer View: Insurer vs market satisfaction, NPS, brand perception (Q46),
              previous insurer sentiment.

Layout: Decision Screen pattern (context bar, narrative, KPIs, 70/30 split, footer).
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
from lib.components.context_bar import render_context_bar
from lib.components.context_footer import render_context_footer
from lib.components.decision_kpi import decision_kpi_row
from lib.components.narrative_panel import render_narrative_compact
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
from lib.formatting import fmt_pct, period_label, FONT
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


# ---------------------------------------------------------------------------
# Market view
# ---------------------------------------------------------------------------

def _render_market_view(df_mkt, filters, period, n_mkt):
    """Market-level satisfaction overview."""
    product = filters["product"]

    # ── Calculate metrics ────────────────────────────────────────
    sat = calc_overall_satisfaction(df_mkt, "Q47")
    nps = calc_nps(df_mkt, "Q48")

    # ── Context bar ──────────────────────────────────────────────
    render_context_bar(
        "Satisfaction & Loyalty",
        product=product,
        period=period,
        n_market=n_mkt,
    )

    # ── KPI row ──────────────────────────────────────────────────
    kpis = [
        {
            "title": "Market Satisfaction (Q47)",
            "value": f"{sat['mean']:.2f}" if sat else "\u2014",
            "sample_n": sat["n"] if sat else None,
            "colour": CI_MAGENTA,
        },
        {
            "title": "Market NPS (Q48)",
            "value": f"{nps['nps']:+.0f}" if nps else "\u2014",
            "sample_n": nps["n"] if nps else None,
            "colour": CI_GREEN if nps and nps["nps"] > 0 else CI_RED if nps and nps["nps"] < 0 else CI_GREY,
        },
    ]
    if nps:
        kpis.append({
            "title": "NPS Breakdown",
            "value": f"{nps['promoters_pct']:.0%} / {nps['passives_pct']:.0%} / {nps['detractors_pct']:.0%}",
            "change": "Promoters / Passives / Detractors",
            "colour": CI_GREY,
        })
    decision_kpi_row(kpis)

    # ── 70 / 30 split ───────────────────────────────────────────
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Satisfaction Distribution
        if sat and sat.get("distribution"):
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; font-weight:700; '
                f'color:{CI_GREY}; margin:16px 0 4px 0;">'
                f'Satisfaction Distribution (Q47)</div>',
                unsafe_allow_html=True,
            )
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
                height=280,
                yaxis=dict(tickformat=".0%", gridcolor=CI_LIGHT_GREY),
                xaxis=dict(title="Satisfaction Score (1-5)"),
                plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
                font=dict(family=FONT, size=11, color=CI_GREY),
                margin=dict(l=10, r=20, t=10, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_secondary:
        # Satisfaction-Retention Matrix
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:700; '
            f'color:{CI_GREY}; margin:16px 0 4px 0;">'
            f'Satisfaction vs Retention</div>',
            unsafe_allow_html=True,
        )

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

    # ── Context footer ───────────────────────────────────────────
    render_context_footer(
        screen_name="satisfaction_market",
        product=product,
        period=period,
        sample_n=n_mkt,
    )


# ---------------------------------------------------------------------------
# Insurer view
# ---------------------------------------------------------------------------

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

    # ── Calculate all metrics upfront (needed for narrative) ─────
    ins_sat = calc_overall_satisfaction(df_ins, "Q47")
    mkt_sat = calc_overall_satisfaction(df_mkt, "Q47")
    ins_nps = calc_nps(df_ins, "Q48")
    mkt_nps = calc_nps(df_mkt, "Q48")

    # ── Context bar ──────────────────────────────────────────────
    render_context_bar(
        "Satisfaction & Loyalty",
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
    ins_sat_val = ins_sat["mean"] if ins_sat else 0
    mkt_sat_val = mkt_sat["mean"] if mkt_sat else 0
    ins_nps_val = ins_nps["nps"] if ins_nps else 0
    mkt_nps_val = mkt_nps["nps"] if mkt_nps else 0

    ins_prev = calc_previous_insurer_satisfaction(df_mkt, insurer)
    mkt_prev = calc_previous_insurer_satisfaction(df_mkt)
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
    render_narrative_compact(narrative, "satisfaction")

    # ── KPI row ──────────────────────────────────────────────────
    sat_gap = (ins_sat_val - mkt_sat_val) if ins_sat and mkt_sat else 0
    sat_trend = "up" if sat_gap > 0 else "down" if sat_gap < 0 else "flat"
    sat_sign = "+" if sat_gap > 0 else ""

    nps_gap = (ins_nps_val - mkt_nps_val) if ins_nps and mkt_nps else 0
    nps_trend = "up" if nps_gap > 0 else "down" if nps_gap < 0 else "flat"
    nps_sign = "+" if nps_gap > 0 else ""

    decision_kpi_row([
        {
            "title": f"{insurer} Satisfaction",
            "value": f"{ins_sat_val:.2f}" if ins_sat else "\u2014",
            "change": f"{sat_sign}{sat_gap:.2f} vs market" if ins_sat and mkt_sat else "",
            "trend": sat_trend,
            "sample_n": n_ins,
            "colour": CI_MAGENTA,
        },
        {
            "title": "Market Satisfaction",
            "value": f"{mkt_sat_val:.2f}" if mkt_sat else "\u2014",
            "sample_n": n_mkt,
            "colour": MARKET_COLOUR,
        },
        {
            "title": f"{insurer} NPS",
            "value": f"{ins_nps_val:+.0f}" if ins_nps else "\u2014",
            "change": f"{nps_sign}{nps_gap:.0f} vs market" if ins_nps and mkt_nps else "",
            "trend": nps_trend,
            "sample_n": n_ins,
            "colour": CI_GREEN if ins_nps_val > 0 else CI_RED if ins_nps_val < 0 else CI_GREY,
        },
        {
            "title": "Market NPS",
            "value": f"{mkt_nps_val:+.0f}" if mkt_nps else "\u2014",
            "sample_n": n_mkt,
            "colour": CI_GREEN if mkt_nps_val > 0 else CI_RED if mkt_nps_val < 0 else CI_GREY,
        },
    ])

    # ── 70 / 30 split ───────────────────────────────────────────
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Brand Perception (Q46)
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:700; '
            f'color:{CI_GREY}; margin:16px 0 4px 0;">'
            f'Brand Perception (Q46)</div>',
            unsafe_allow_html=True,
        )

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
                st.info("No Q46 data available for this insurer/market comparison.")
        else:
            q46_cols = [c for c in df_mkt.columns if c.startswith("Q46_")]
            if q46_cols:
                st.info(f"Q46 columns found ({len(q46_cols)}) but no data for this insurer/market.")
            else:
                st.warning(
                    "No Q46 brand perception data available. "
                    "Q46 columns are missing from the cached data. "
                    "Check whether Q46 rows exist in the OtherData table in Power BI "
                    "(with a non-null Subject column)."
                )

    with col_secondary:
        # Departed Sentiment (Q40a / Q40b)
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">'
            f'Departed Sentiment</div>',
            unsafe_allow_html=True,
        )

        if ins_prev and ins_prev.get("n", 0) >= MIN_BASE_REASON:
            dep_sat = ins_prev.get("mean_q40a")
            dep_nps = ins_prev.get("nps")
            mkt_dep_sat = mkt_prev.get("mean_q40a") if mkt_prev else None

            sat_str = f"{dep_sat:.2f}/5" if dep_sat is not None else "\u2014"
            mkt_sat_str = f"{mkt_dep_sat:.2f}/5" if mkt_dep_sat is not None else "\u2014"
            nps_str = f"{dep_nps:+.0f}" if dep_nps is not None else "\u2014"
            nps_colour = CI_GREEN if dep_nps and dep_nps > 0 else CI_RED if dep_nps and dep_nps < 0 else CI_GREY

            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; color:{CI_GREY}; padding:6px 0;">'
                f'<div style="padding:3px 0;">Departed Sat: <span style="font-weight:700; color:{CI_MAGENTA};">{sat_str}</span></div>'
                f'<div style="padding:3px 0;">Market Departed: <span style="font-weight:700;">{mkt_sat_str}</span></div>'
                f'<div style="padding:3px 0;">Departed NPS: <span style="font-weight:700; color:{nps_colour};">{nps_str}</span></div>'
                f'<div style="padding:3px 0; color:{CI_GREY};">n={ins_prev["n"]:,} switchers from {insurer}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            n_dep = ins_prev["n"] if ins_prev else 0
            st.markdown(
                render_suppression_html(f"{insurer} (Departed Satisfaction)", n_dep, MIN_BASE_REASON),
                unsafe_allow_html=True,
            )

        # Cross-screen links
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">Explore</div>',
            unsafe_allow_html=True,
        )
        if st.button("Reasons & Drivers", key="satisfaction_to_reasons"):
            from lib.state import navigate_to
            navigate_to("reasons")
        if st.button("Claims Intelligence", key="satisfaction_to_claims"):
            from lib.state import navigate_to
            navigate_to("claims")

    # ── Context footer ───────────────────────────────────────────
    render_context_footer(
        screen_name="satisfaction",
        product=product,
        period=period,
        sample_n=n_ins,
    )

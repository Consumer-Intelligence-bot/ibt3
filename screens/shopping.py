"""
Screen 3: Shopping Behaviour.

Market View: Shopping rate KPIs, shopping rate trend by month, Q8 reasons for shopping,
             Q19 reasons for not shopping.
Insurer View: Shopping rate vs market, cohort heat map, insurer-specific reasons.

Layout: Decision Screen pattern (context bar, narrative, KPIs, 70/30 split, footer).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.cohort_heatmap import calc_cohort_heatmap
from lib.analytics.demographics import apply_filters
from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.flow_display import calc_wilson_ci, format_ci_range
from lib.analytics.rates import (
    calc_shopping_rate,
    calc_switching_rate,
    calc_retention_rate,
    calc_conversion_rate,
)
from lib.analytics.reasons import calc_reason_ranking, calc_reason_comparison, calc_reason_index
from lib.chart_export import render_suppression_html
from lib.components.cohort_heatmap import render_cohort_heatmap
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
    FONT,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, period_label
from lib.question_ref import get_question_text
from lib.state import format_year_month, get_ss_data


def render(filters: dict):
    """Render the Shopping Behaviour screen."""
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
    """Market-level shopping behaviour overview."""
    product = filters["product"]

    # -- Calculate rates --
    shopping_rate = calc_shopping_rate(df_mkt)
    switching_rate = calc_switching_rate(df_mkt)
    retention_rate = calc_retention_rate(df_mkt)
    conversion_rate = calc_conversion_rate(df_mkt)

    # -- Context bar --
    render_context_bar(
        "Shopping Behaviour",
        product=product,
        period=period,
        n_market=n_mkt,
    )

    # -- KPI row (market view: neutral colours, no insurer comparison) --
    decision_kpi_row([
        {
            "title": "Shopping Rate",
            "value": fmt_pct(shopping_rate),
            "sample_n": n_mkt,
            "colour": CI_GREY,
        },
        {
            "title": "Conversion Rate",
            "value": fmt_pct(conversion_rate),
            "caption": "% of shoppers who switched to a new insurer after comparing quotes",
            "sample_n": n_mkt,
            "colour": CI_GREY,
        },
        {
            "title": "Switching Rate",
            "value": fmt_pct(switching_rate),
            "sample_n": n_mkt,
            "colour": CI_GREY,
        },
        {
            "title": "Retention Rate",
            "value": fmt_pct(retention_rate),
            "sample_n": n_mkt,
            "colour": CI_GREY,
        },
    ])

    # -- 70 / 30 split --
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Shopping rate trend by month
        if "RenewalYearMonth" in df_mkt.columns:
            months = sorted(df_mkt["RenewalYearMonth"].dropna().unique().astype(int))
            trend_rows = []
            for m in months:
                df_month = df_mkt[df_mkt["RenewalYearMonth"] == m]
                sr = calc_shopping_rate(df_month)
                if sr is not None:
                    trend_rows.append({
                        "month": m,
                        "label": format_year_month(m),
                        "shopping_rate": sr,
                        "n": len(df_month),
                    })

            if trend_rows:
                trend_df = pd.DataFrame(trend_rows)
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=trend_df["label"],
                    y=trend_df["shopping_rate"],
                    mode="lines+markers",
                    line=dict(color=CI_MAGENTA, width=2),
                    marker=dict(size=5),
                    hovertemplate="<b>%{x}</b><br>Shopping: %{y:.1%}<extra></extra>",
                ))
                fig.update_layout(
                    height=300,
                    yaxis=dict(title="Shopping Rate", tickformat=".0%", gridcolor=CI_LIGHT_GREY),
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
        # Q8: Why customers shop
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin-bottom:4px;">Why New Customers Shopped (Q8)</div>'
            f'<div style="font-size:10px; color:{CI_GREY}; margin-bottom:8px; font-style:italic;">'
            f'Why new customers shopped around before joining their current insurer</div>',
            unsafe_allow_html=True,
        )
        n_shoppers = int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0

        if n_shoppers < MIN_BASE_REASON:
            st.info("Insufficient shoppers for Q8 analysis (below minimum base).")
        else:
            q8 = calc_reason_ranking(df_mkt, "Q8", top_n=5)
            if q8:
                _render_reason_bar(q8, CI_MAGENTA)
            else:
                st.info("No Q8 data available.")

        # Q19: Why customers don't shop
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin:12px 0 8px 0;">Why Customers Don\'t Shop (Q19)</div>',
            unsafe_allow_html=True,
        )
        n_non_shoppers = n_mkt - (int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0)

        if n_non_shoppers < MIN_BASE_REASON:
            st.info("Insufficient non-shoppers for Q19 analysis (below minimum base).")
        else:
            q19 = calc_reason_ranking(df_mkt, "Q19", top_n=5)
            if q19:
                _render_reason_bar(q19, CI_GREEN)
            else:
                st.info("No Q19 data available.")

    # -- Context footer --
    render_context_footer(
        screen_name="shopping_market",
        product=product,
        period=period,
        sample_n=n_mkt,
    )


# ---------------------------------------------------------------------------
# Insurer view
# ---------------------------------------------------------------------------

def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer-level shopping analysis with cohort heat map."""
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

    # -- Calculate all metrics upfront (needed for narrative) --
    ins_shopping = calc_shopping_rate(df_ins)
    mkt_shopping = calc_shopping_rate(df_mkt)
    ins_conversion = calc_conversion_rate(df_ins)
    mkt_conversion = calc_conversion_rate(df_mkt)

    # -- Context bar --
    render_context_bar(
        "Shopping Behaviour",
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
    narrative = generate_screen_narrative("shopping", {
        "insurer": insurer,
        "product": product,
        "shopping_rate": ins_shopping or 0,
        "mkt_shopping_rate": mkt_shopping or 0,
        "conversion_rate": ins_conversion or 0,
        "mkt_conversion_rate": mkt_conversion or 0,
    })
    render_narrative_compact(narrative, "shopping")

    # -- KPI row --
    shopping_gap = ((ins_shopping or 0) - (mkt_shopping or 0)) * 100
    shopping_trend = "up" if shopping_gap > 0 else "down" if shopping_gap < 0 else "flat"
    shopping_sign = "+" if shopping_gap > 0 else ""

    conversion_gap = ((ins_conversion or 0) - (mkt_conversion or 0)) * 100
    conversion_trend = "up" if conversion_gap > 0 else "down" if conversion_gap < 0 else "flat"
    conversion_sign = "+" if conversion_gap > 0 else ""

    # Wilson 95% CI on shopping and conversion rates
    shop_ci = calc_wilson_ci(
        int((ins_shopping or 0) * n_ins), n_ins
    ) if ins_shopping is not None else None
    conv_ci = calc_wilson_ci(
        int((ins_conversion or 0) * n_ins), n_ins
    ) if ins_conversion is not None else None

    decision_kpi_row([
        {
            "title": "Shopping Rate",
            "value": fmt_pct(ins_shopping),
            "change": f"{shopping_sign}{shopping_gap:.1f}pp vs market",
            "trend": shopping_trend,
            "caption": format_ci_range(*shop_ci) if shop_ci else "",
            "sample_n": n_ins,
            "colour": CI_MAGENTA,
        },
        {
            "title": "Conversion Rate",
            "value": fmt_pct(ins_conversion),
            "change": f"{conversion_sign}{conversion_gap:.1f}pp vs market",
            "trend": conversion_trend,
            "caption": (format_ci_range(*conv_ci) if conv_ci else "") + (" — % shoppers who switched" if conv_ci else "% shoppers who switched"),
            "sample_n": n_ins,
            "colour": CI_RED,
        },
        {
            "title": "Sample Share",
            "value": fmt_pct(n_ins / n_mkt) if n_mkt else "--",
            "change": "of market respondents",
            "sample_n": n_ins,
            "colour": CI_GREY,
        },
    ])

    # -- 70 / 30 split --
    col_primary, col_secondary = st.columns([7, 3])

    with col_primary:
        # Cohort heat map
        heatmap_df = calc_cohort_heatmap(df_ins, df_mkt)
        render_cohort_heatmap(heatmap_df, insurer)

        # Q8 insurer vs market comparison
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
            f'color:{CI_MAGENTA}; margin:16px 0 2px 0;">'
            f'Why new {insurer} customers shopped around before joining (Q8)</div>',
            unsafe_allow_html=True,
        )
        q8_comp = calc_reason_comparison(df_mkt, "Q8", insurer, top_n=5)
        if q8_comp:
            _render_comparison_columns(q8_comp, insurer)
            # Index table: how insurer's shoppers compare to market shoppers
            indexed = calc_reason_index(
                q8_comp.get("insurer", []),
                q8_comp.get("market", []),
            )
            if indexed:
                _render_reason_index_table(indexed)
        else:
            st.info("No Q8 data available.")

        # Q19 insurer vs market comparison
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:700; '
            f'color:{CI_GREEN}; margin:16px 0 2px 0;">'
            f'Why existing {insurer} customers chose not to shop around (Q19)</div>',
            unsafe_allow_html=True,
        )
        q19_comp = calc_reason_comparison(df_mkt, "Q19", insurer, top_n=5)
        if q19_comp:
            _render_comparison_columns(q19_comp, insurer)
        else:
            st.info("No Q19 data available.")

    with col_secondary:
        # Cross-screen links
        st.markdown(
            f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">Explore</div>',
            unsafe_allow_html=True,
        )
        if st.button("Channels & PCWs", key="shopping_to_channels"):
            from lib.state import navigate_to
            navigate_to("channels")
        if st.button("Pre-Renewal Context", key="shopping_to_prerenewal"):
            from lib.state import navigate_to
            navigate_to("pre_renewal")
        if st.button("Compare Insurers", key="shopping_to_comparison"):
            from lib.state import navigate_to
            navigate_to("comparison")

    # -- Context footer --
    render_context_footer(
        screen_name="shopping",
        product=product,
        period=period,
        sample_n=n_ins,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _render_reason_bar(reasons: list[dict], colour: str):
    """Render a compact horizontal bar chart for reasons."""
    df = pd.DataFrame(reasons)
    pct_col = "rank1_pct" if "rank1_pct" in df.columns else "mention_pct"

    fig = go.Figure(go.Bar(
        x=df[pct_col],
        y=df["reason"],
        orientation="h",
        marker_color=colour,
        text=[f"{p:.0%}" for p in df[pct_col]],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1%}<extra></extra>",
    ))

    fig.update_layout(
        xaxis_tickformat=".0%",
        height=max(200, len(df) * 35 + 60),
        margin=dict(l=10, r=40, t=10, b=20),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        yaxis=dict(autorange="reversed"),
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_reason_index_table(indexed: list[dict]):
    """Render a compact index table showing insurer vs market over/under-index."""
    rows_html = (
        f'<table style="width:100%; border-collapse:collapse; font-size:11px; margin-top:6px;">'
        f'<thead><tr style="border-bottom:2px solid {CI_LIGHT_GREY};">'
        f'<th style="text-align:left; padding:4px 6px; color:{CI_GREY};">Reason</th>'
        f'<th style="text-align:right; padding:4px 6px; color:{CI_GREY};">Index</th>'
        f'</tr></thead><tbody>'
    )
    for row in indexed:
        index_val = row.get("index")
        if index_val is None:
            index_str = "\u2014"
            colour = CI_GREY
        else:
            index_str = f"{index_val:.0f}"
            colour = CI_GREEN if index_val >= 110 else (CI_RED if index_val <= 90 else CI_GREY)
        rows_html += (
            f'<tr style="border-bottom:1px solid {CI_LIGHT_GREY};">'
            f'<td style="padding:4px 6px; color:{CI_GREY};">{row["reason"]}</td>'
            f'<td style="text-align:right; padding:4px 6px; color:{colour}; '
            f'font-weight:bold;">{index_str}</td>'
            f'</tr>'
        )
    rows_html += '</tbody></table>'
    st.markdown(
        f'<div style="font-size:10px; color:{CI_GREY}; margin-top:6px; font-style:italic;">'
        f'Index: 100 = market average. Above 110 = over-index (dark green), below 90 = under-index (red).</div>',
        unsafe_allow_html=True,
    )
    st.markdown(rows_html, unsafe_allow_html=True)


def _render_comparison_columns(comparison: dict, insurer: str):
    """Render insurer vs market reason columns."""
    col_ins, col_mkt = st.columns(2)

    with col_ins:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
            f'color:{CI_MAGENTA}; margin-bottom:6px;">{insurer}</div>',
            unsafe_allow_html=True,
        )
        for r in comparison.get("insurer", []):
            pct = r.get("rank1_pct", r.get("mention_pct", 0))
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                f'{r["reason"]} <span style="float:right; color:{CI_MAGENTA}; '
                f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                unsafe_allow_html=True,
            )

    with col_mkt:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
            f'color:{MARKET_COLOUR}; margin-bottom:6px;">Market</div>',
            unsafe_allow_html=True,
        )
        for r in comparison.get("market", []):
            pct = r.get("rank1_pct", r.get("mention_pct", 0))
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                f'{r["reason"]} <span style="float:right; color:{MARKET_COLOUR}; '
                f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                unsafe_allow_html=True,
            )

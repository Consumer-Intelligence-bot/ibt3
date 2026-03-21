"""
Screen 3: Shopping Behaviour.

Market View: Shopping rate KPIs, shopping rate trend by month, Q8 reasons for shopping,
             Q19 reasons for not shopping.
Insurer View: Shopping rate vs market, cohort heat map, insurer-specific reasons.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.cohort_heatmap import calc_cohort_heatmap
from lib.analytics.demographics import apply_filters
from lib.analytics.rates import (
    calc_shopping_rate,
    calc_switching_rate,
    calc_retention_rate,
    calc_conversion_rate,
)
from lib.analytics.reasons import calc_reason_ranking, calc_reason_comparison
from lib.chart_export import apply_export_metadata, render_suppression_html
from lib.components.cohort_heatmap import render_cohort_heatmap
from lib.components.kpi_cards import kpi_card
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT
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


def _render_market_view(df_mkt, filters, period, n_mkt):
    """Market-level shopping behaviour overview."""
    st.subheader("Shopping Behaviour: Market View")

    # --- KPI cards ---
    shopping_rate = calc_shopping_rate(df_mkt)
    switching_rate = calc_switching_rate(df_mkt)
    retention_rate = calc_retention_rate(df_mkt)
    conversion_rate = calc_conversion_rate(df_mkt)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card("Shopping Rate", fmt_pct(shopping_rate), f"n={n_mkt:,}", CI_MAGENTA)
    with col2:
        kpi_card("Conversion Rate", fmt_pct(conversion_rate), "Shoppers who switched", CI_RED)
    with col3:
        kpi_card("Switching Rate", fmt_pct(switching_rate), f"n={n_mkt:,}", CI_RED)
    with col4:
        kpi_card("Retention Rate", fmt_pct(retention_rate), f"n={n_mkt:,}", CI_GREEN)

    # --- Shopping rate by month ---
    section_divider("Shopping Rate Trend")

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

    # --- Why shop (Q8) and Why not shop (Q19) side by side ---
    section_divider("Reasons for Shopping / Not Shopping")

    col_q8, col_q19 = st.columns(2)

    with col_q8:
        st.markdown(f"**Why Customers Shop (Q8)**")
        st.caption(get_question_text("Q8"))
        n_shoppers = int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0

        if n_shoppers < MIN_BASE_REASON:
            st.info(f"Insufficient shoppers ({n_shoppers:,}) for Q8 analysis.")
        else:
            q8 = calc_reason_ranking(df_mkt, "Q8", top_n=5)
            if q8:
                _render_reason_bar(q8, CI_MAGENTA)
            else:
                st.info("No Q8 data available.")

    with col_q19:
        st.markdown(f"**Why Customers Don't Shop (Q19)**")
        st.caption(get_question_text("Q19"))
        n_non_shoppers = n_mkt - (int(df_mkt["IsShopper"].sum()) if "IsShopper" in df_mkt.columns else 0)

        if n_non_shoppers < MIN_BASE_REASON:
            st.info(f"Insufficient non-shoppers ({n_non_shoppers:,}) for Q19 analysis.")
        else:
            q19 = calc_reason_ranking(df_mkt, "Q19", top_n=5)
            if q19:
                _render_reason_bar(q19, CI_GREEN)
            else:
                st.info("No Q19 data available.")

    # Footer
    st.markdown("---")
    st.caption(f"Shopping Behaviour | Market | {filters['product']} | {period} | n={n_mkt:,}")


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

    st.subheader(f"Shopping Behaviour: {insurer}")

    # Period banner
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

    # --- KPI cards: insurer vs market ---
    section_divider("Shopping Metrics")

    ins_shopping = calc_shopping_rate(df_ins)
    mkt_shopping = calc_shopping_rate(df_mkt)
    ins_conversion = calc_conversion_rate(df_ins)
    mkt_conversion = calc_conversion_rate(df_mkt)

    col1, col2, col3 = st.columns(3)
    with col1:
        gap = ((ins_shopping or 0) - (mkt_shopping or 0)) * 100
        sign = "+" if gap > 0 else ""
        kpi_card(
            "Shopping Rate",
            fmt_pct(ins_shopping),
            f"Market: {fmt_pct(mkt_shopping)} ({sign}{gap:.1f}pp)",
            CI_MAGENTA,
        )
    with col2:
        kpi_card(
            "Conversion Rate",
            fmt_pct(ins_conversion),
            f"Market: {fmt_pct(mkt_conversion)}",
            CI_RED,
        )
    with col3:
        kpi_card("Insurer Base", f"{n_ins:,}", f"Market: {n_mkt:,}", CI_GREY)

    # --- Cohort Heat Map ---
    section_divider("Cohort Heat Map: Demographic Segments vs Market")

    heatmap_df = calc_cohort_heatmap(df_ins, df_mkt)
    render_cohort_heatmap(heatmap_df, insurer)

    # --- Insurer vs Market reasons (Q8, Q19) ---
    section_divider("Why Customers Shop (Q8)")
    st.caption(get_question_text("Q8"))

    q8_comp = calc_reason_comparison(df_mkt, "Q8", insurer, top_n=5)
    if q8_comp:
        _render_comparison_columns(q8_comp, insurer)
    else:
        st.info("No Q8 data available.")

    section_divider("Why Customers Don't Shop (Q19)")
    st.caption(get_question_text("Q19"))

    q19_comp = calc_reason_comparison(df_mkt, "Q19", insurer, top_n=5)
    if q19_comp:
        _render_comparison_columns(q19_comp, insurer)
    else:
        st.info("No Q19 data available.")

    # Footer
    st.markdown("---")
    st.caption(
        f"Shopping Behaviour | {insurer} | {filters['product']} | {period} | "
        f"Insurer n={n_ins:,} | Market n={n_mkt:,}"
    )


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

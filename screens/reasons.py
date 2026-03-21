"""
Screen 6: Reasons & Drivers.

Market View: Top reasons for shopping (Q8), not shopping (Q19), staying (Q18),
             leaving (Q31), and choosing (Q33).
Insurer View: Insurer vs market comparison for each reason set.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.reasons import calc_reason_ranking, calc_reason_comparison
from lib.chart_export import apply_export_metadata, render_suppression_html
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_panel
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    MARKET_COLOUR,
    MIN_BASE_REASON,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT
from lib.question_ref import get_question_text
from lib.state import get_ss_data


# Reason question definitions: (q_code, title, base_description, filter_fn)
_MARKET_PANELS = [
    ("Q8", "Why Customers Shop", "Shoppers (Q7=Yes)", lambda df: df[df["IsShopper"]] if "IsShopper" in df.columns else df),
    ("Q19", "Why Customers Don't Shop", "Non-shoppers (Q7=No)", lambda df: df[~df["IsShopper"]] if "IsShopper" in df.columns else df),
    ("Q18", "Why Customers Stay After Shopping", "Shoppers who stayed", lambda df: df[(df["IsShopper"]) & (~df["IsSwitcher"])] if "IsShopper" in df.columns and "IsSwitcher" in df.columns else df),
    ("Q31", "Why Customers Leave", "Switchers", lambda df: df[df["IsSwitcher"]] if "IsSwitcher" in df.columns else df),
    ("Q33", "Why Customers Choose Their New Insurer", "Switchers", lambda df: df[df["IsSwitcher"]] if "IsSwitcher" in df.columns else df),
]


def render(filters: dict):
    """Render the Reasons & Drivers screen."""
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
    """Market-level reason panels: 5 question sets."""
    st.subheader("Reasons & Drivers: Market View")

    for q_code, title, base_desc, filter_fn in _MARKET_PANELS:
        section_divider(f"{title} ({q_code})")
        st.caption(get_question_text(q_code))

        base_df = filter_fn(df_mkt)
        n_base = len(base_df)

        if n_base < MIN_BASE_REASON:
            st.info(
                f"Insufficient base ({n_base:,}) for {q_code} analysis "
                f"(minimum {MIN_BASE_REASON}). {base_desc}."
            )
            continue

        reasons = calc_reason_ranking(df_mkt, q_code, top_n=5)
        if not reasons:
            st.info(f"No {q_code} data available.")
            continue

        _render_reason_bar(reasons, q_code, title, period, n_base)

    # Footer
    st.markdown("---")
    st.caption(f"Reasons & Drivers | Market | {filters['product']} | {period} | n={n_mkt:,}")


def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer vs market comparison for each reason set."""
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

    st.subheader(f"Reasons & Drivers: {insurer}")

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

    # For Q18 (stay reasons), filter to shoppers who stayed
    _INSURER_PANELS = [
        ("Q8", "Why Customers Shop", "shoppers"),
        ("Q19", "Why Customers Don't Shop", "non-shoppers"),
        ("Q18", "Why Customers Stay After Shopping", "shoppers who stayed"),
        ("Q31", "Why Customers Leave", "switchers from this insurer"),
        ("Q33", "Why Customers Choose New Insurer", "switchers to this insurer"),
        ("Q28", "What Would Bring Customers Back", "switchers from this insurer"),
    ]

    for q_code, title, base_desc in _INSURER_PANELS:
        section_divider(f"{title} ({q_code})")
        st.caption(get_question_text(q_code))

        comparison = calc_reason_comparison(df_mkt, q_code, insurer, top_n=5)
        if not comparison:
            st.info(f"No {q_code} data available.")
            continue

        ins_reasons = comparison.get("insurer", [])
        mkt_reasons = comparison.get("market", [])

        if not ins_reasons and not mkt_reasons:
            st.info(f"No {q_code} data available.")
            continue

        _render_reason_comparison(ins_reasons, mkt_reasons, insurer, q_code)

    # --- AI Narrative ---
    section_divider("AI Narrative")
    top_stay = calc_reason_ranking(df_mkt, "Q18", insurer, top_n=1)
    top_leave = calc_reason_ranking(df_mkt, "Q31", insurer, top_n=1)
    top_shop = calc_reason_ranking(df_mkt, "Q8", insurer, top_n=1)
    narrative = generate_screen_narrative("reasons", {
        "insurer": insurer,
        "product": filters["product"],
        "top_stay_reason": top_stay[0]["reason"] if top_stay else "N/A",
        "top_leave_reason": top_leave[0]["reason"] if top_leave else "N/A",
        "top_shop_reason": top_shop[0]["reason"] if top_shop else "N/A",
    })
    render_narrative_panel(narrative, "reasons")

    # --- Cross-screen links ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Switching & Flows", key="reasons_to_switching"):
            from lib.state import navigate_to
            navigate_to("switching")
    with col2:
        if st.button("View Satisfaction & Loyalty", key="reasons_to_satisfaction"):
            from lib.state import navigate_to
            navigate_to("satisfaction")

    # Footer
    st.markdown("---")
    st.caption(
        f"Reasons & Drivers | {insurer} | {filters['product']} | {period} | "
        f"Insurer n={n_ins:,} | Market n={n_mkt:,}"
    )


def _render_reason_bar(reasons: list[dict], q_code: str, title: str, period: str, n_base: int):
    """Render a horizontal bar chart for market-level reasons."""
    df = pd.DataFrame(reasons)

    # Use rank1_pct for ranked questions, mention_pct for multi-select
    pct_col = "rank1_pct" if "rank1_pct" in df.columns else "mention_pct"

    fig = go.Figure(go.Bar(
        x=df[pct_col],
        y=df["reason"],
        orientation="h",
        marker_color=CI_MAGENTA,
        text=[f"{p:.0%}" for p in df[pct_col]],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1%}<extra></extra>",
    ))

    fig.update_layout(
        xaxis_tickformat=".0%",
        height=max(250, len(df) * 40 + 80),
        margin=dict(l=10, r=50, t=40, b=60),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        yaxis=dict(autorange="reversed"),
    )

    apply_export_metadata(
        fig,
        title=f"{title} \u2014 Top 5",
        period=period,
        base=n_base,
        question=q_code,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_reason_comparison(
    ins_reasons: list[dict],
    mkt_reasons: list[dict],
    insurer: str,
    q_code: str,
):
    """Render insurer vs market dual-column reason comparison."""
    col_ins, col_mkt = st.columns(2)

    with col_ins:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
            f'color:{CI_MAGENTA}; margin-bottom:6px;">{insurer}</div>',
            unsafe_allow_html=True,
        )
        for r in ins_reasons:
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
        for r in mkt_reasons:
            pct = r.get("rank1_pct", r.get("mention_pct", 0))
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                f'{r["reason"]} <span style="float:right; color:{MARKET_COLOUR}; '
                f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                unsafe_allow_html=True,
            )
